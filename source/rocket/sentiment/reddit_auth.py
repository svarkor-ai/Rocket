"""Reddit OAuth 2.0 authentication flow.

Supports two modes:
1. Device flow (headless) — for servers without browser
2. PKCE browser flow (full auth) — opens browser on local machine

Credentials are stored in ~/.hermes/.secrets/svarkor.env
"""
import os
import json
import time
import logging
import secrets
import base64
from urllib.request import urlopen, Request
from urllib.error import URLError

logger = logging.getLogger(__name__)

SECRETS_FILE = os.path.expanduser("~/.hermes/.secrets/svarkor.env")

# Reddit OAuth endpoints
REDDIT_AUTH_URL = "https://www.reddit.com/api/v1/authorize"
REDDIT_TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
REDDIT_API_BASE = "https://oauth.reddit.com"


def _load_env_secrets():
    """Load Reddit credentials from svarkor.env."""
    client_id = None
    client_secret = None

    if os.path.exists(SECRETS_FILE):
        with open(SECRETS_FILE) as f:
            for line in f:
                line = line.strip()
                if line.startswith('#') or '=' not in line:
                    continue
                key, _, val = line.partition('=')
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if key == 'REDDIT_CLIENT_ID':
                    client_id = val
                elif key == 'REDDIT_CLIENT_SECRET':
                    client_secret = val

    return client_id, client_secret


def _save_env_secrets(client_id, client_secret):
    """Save Reddit credentials to svarkor.env (create if needed)."""
    os.makedirs(os.path.dirname(SECRETS_FILE), exist_ok=True)

    if os.path.exists(SECRETS_FILE):
        with open(SECRETS_FILE) as f:
            lines = f.readlines()
    else:
        lines = []

    # Remove existing Reddit keys if present
    lines = [line for line in lines if not line.strip().startswith('REDDIT_')]

    lines.append('\n# Reddit OAuth credentials for rocket-stock-scanner\n')
    lines.append(f'REDDIT_CLIENT_ID={client_id}\n')
    lines.append(f'REDDIT_CLIENT_SECRET={client_secret}\n')

    with open(SECRETS_FILE, 'w') as f:
        f.writelines(lines)

    logger.info(f"Saved Reddit credentials to {SECRETS_FILE}")


# ─── Device flow (headless server) ───────────────────────────────────────

def authenticate_device(client_id=None, client_secret=None, scopes=None):
    """Authenticate using Reddit's device flow (no browser needed).
    
    Returns (access_token, refresh_token, expires_at) or raises.
    """
    if client_id is None or client_secret is None:
        client_id, client_secret = _load_env_secrets()

    if not client_id or not client_secret:
        raise ValueError(
            "No Reddit credentials found. "
            "Please create a Reddit OAuth app at https://www.reddit.com/prefs/apps "
            "and save REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET in ~/.hermes/.secrets/svarkor.env"
        )

    if scopes is None:
        scopes = ['identity', 'read', 'subreddit']

    # Step 1: Get device code
    device_url = "https://www.reddit.com/api/v1/device"
    data = f"device_id={secrets.token_hex(16)}&scope={'+'.join(scopes)}".encode()
    headers = {
        'Authorization': f'Basic {base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()}',
        'Content-Type': 'application/x-www-form-urlencoded',
        'User-Agent': 'rocket-stock-scanner/1.0'
    }

    req = Request(device_url, data=data, headers=headers, method='POST')
    resp = urlopen(req, timeout=15)
    device_data = json.loads(resp.read().decode())

    user_code = device_data['user_code']
    device_code = device_data['device_code']
    expires_in = device_data['expires_in']
    interval = device_data['interval']

    print("\n🔐 Reddit OAuth Device Flow")
    print(f"   Go to: {device_data['verification_uri']}")
    print(f"   Enter code: {user_code}")
    print(f"   (expires in {expires_in}s)")

    # Step 2: Poll for token
    token_url = "https://www.reddit.com/api/v1/access_token"
    start = time.time()

    while time.time() - start < expires_in:
        poll_data = f"grant_type=urn:ietf:params:oauth:grant-type:device_code&device_code={device_code}".encode()
        poll_req = Request(token_url, data=poll_data, headers=headers, method='POST')

        try:
            resp = urlopen(poll_req, timeout=10)
            token_data = json.loads(resp.read().decode())

            access_token = token_data['access_token']
            refresh_token = token_data.get('refresh_token', '')
            expires_at = time.time() + token_data['expires_in']

            logger.info("Reddit authentication successful!")
            return {
                'access_token': access_token,
                'refresh_token': refresh_token,
                'expires_at': expires_at,
                'client_id': client_id,
                'client_secret': client_secret
            }
        except URLError as e:
            err = e.read().decode() if hasattr(e, 'read') else str(e)
            if 'authorization_pending' in err or 'slow_down' in err:
                time.sleep(interval)
                continue
            raise

    raise TimeoutError("Reddit device flow timed out. Please try again.")


# ─── Session token manager ──────────────────────────────────────────────

class RedditSession:
    """Manages Reddit OAuth sessions with automatic refresh."""

    def __init__(self, client_id=None, client_secret=None, token_file=None):
        if client_id is None or client_secret is None:
            client_id, client_secret = _load_env_secrets()

        self.client_id = client_id
        self.client_secret = client_secret
        self.token_file = token_file or os.path.expanduser("~/.hermes/.cache/reddit_tokens.json")
        self._token = None

        # Load saved tokens if available
        self._load_saved_tokens()

    def _load_saved_tokens(self):
        """Load saved tokens from disk."""
        if os.path.exists(self.token_file):
            try:
                with open(self.token_file) as f:
                    data = json.load(f)
                if data.get('expires_at', 0) > time.time():
                    self._token = data
                    logger.info("Loaded saved Reddit tokens")
                    return
            except Exception:
                logger.warning("Failed to load saved tokens")

    def _save_tokens(self):
        """Save tokens to disk."""
        os.makedirs(os.path.dirname(self.token_file), exist_ok=True)
        with open(self.token_file, 'w') as f:
            json.dump(self._token, f, indent=2)

    def authenticate(self, scopes=None):
        """Authenticate using device flow."""
        token = authenticate_device(
            client_id=self.client_id,
            client_secret=self.client_secret,
            scopes=scopes
        )
        self._token = token
        self._save_tokens()
        return token

    def ensure_authenticated(self, scopes=None):
        """Ensure we have a valid token, authenticate if needed."""
        if self._token and self._token.get('expires_at', 0) > time.time():
            return True

        logger.info("Reddit token expired or not set. Authenticating...")
        if self.client_id and self.client_secret:
            self.authenticate(scopes)
            return True

        raise ValueError(
            "No Reddit credentials found. "
            "Please create a Reddit OAuth app and save credentials."
        )

    def refresh_token(self):
        """Refresh the access token using the refresh token."""
        if not self._token or not self._token.get('refresh_token'):
            return False

        data = f"grant_type=refresh_token&refresh_token={self._token['refresh_token']}".encode()
        headers = {
            'Authorization': f'Basic {base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()}',
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': 'rocket-stock-scanner/1.0'
        }

        req = Request(REDDIT_TOKEN_URL, data=data, headers=headers, method='POST')
        try:
            resp = urlopen(req, timeout=15)
            token_data = json.loads(resp.read().decode())

            self._token = {
                'access_token': token_data['access_token'],
                'refresh_token': token_data.get('refresh_token', self._token.get('refresh_token', '')),
                'expires_at': time.time() + token_data['expires_in'],
                'client_id': self.client_id,
                'client_secret': self.client_secret
            }
            self._save_tokens()
            return True
        except Exception:
            logger.warning("Token refresh failed")
            return False

    def get_headers(self):
        """Get authenticated request headers."""
        self.ensure_authenticated()
        if not self._token.get('access_token'):
            raise ValueError("No access token available")

        return {
            'Authorization': f'Bearer {self._token["access_token"]}',
            'User-Agent': 'rocket-stock-scanner/1.0'
        }

    def search_subreddit(self, subreddit, query, limit=25, sort='top', time_filter='week'):
        """Search posts in a subreddit."""
        url = f"{REDDIT_API_BASE}/r/{subreddit}/search.json"
        params = {
            'q': query,
            'limit': min(limit, 100),
            'sort': sort,
            't': time_filter,
            'restrict_sr': 'on',
        }
        return self._get_json(url, params=params)

    def get_subreddit_posts(self, subreddit, limit=50, sort='top', time_filter='week'):
        """Get top posts from a subreddit."""
        url = f"{REDDIT_API_BASE}/r/{subreddit}.json"
        params = {
            'limit': min(limit, 100),
            'sort': sort,
            't': time_filter,
        }
        return self._get_json(url, params=params)

    def _get_json(self, url, params=None):
        """Make an authenticated GET request and return JSON."""
        import urllib.parse

        headers = self.get_headers()

        if params:
            query = urllib.parse.urlencode(params)
            url = f"{url}?{query}"

        req = Request(url, headers=headers, method='GET')
        try:
            resp = urlopen(req, timeout=30)
            data = json.loads(resp.read().decode())
            return data
        except Exception:
            logger.warning("Reddit API request failed")
            return None

    def close(self):
        """Release session resources."""
        pass

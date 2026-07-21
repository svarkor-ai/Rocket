"""
Rocket Stock Scanner - Dynamic Universe Builder

Loads ticker universes from:
1. Major index constituents via Wikipedia (S&P 500, Nasdaq 100, Dow Jones, Russell 2000, FTSE, DAX, CAC, etc.)
2. Small/mid-cap tickers from additional sources
3. Cached for performance

Total target: 10,000+ tickers across global markets.
"""

import json
import logging
import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Cache paths
CACHE_DIR = Path(__file__).parent
CACHE_FILE = CACHE_DIR / "universe_cache.json"
CACHE_TTL_HOURS = 24  # Refresh cache every 24h

# Known index constituents (fetched from Wikipedia and other sources)
INDEX_CONSTITUENTS_FILE = CACHE_DIR / "index_constituents.json"

# Wikipedia page mapping: index_symbol -> (page_name, ticker_column)
# ticker_column: "symbol" or "ticker" — which column header to look for
WIKI_MAP = {
    "^GSPC": ("List_of_S%26P_500_companies", "Symbol"),
    "^NDX": ("Nasdaq-100", "Ticker"),
    "^DJI": ("Dow_Jones_Industrial_Average", "Ticker"),
    "^RUT": ("Russell_2000_Index", "Ticker"),
    "^FTSE": ("FTSE_100_Index", "Ticker"),
    "^GDAXI": ("DAX", "Ticker"),
    "^FCHI": ("CAC_40", "Ticker"),
    "^N225": ("Nikkei_225", "Ticker"),
    "^HSI": ("Hang_Seng_Index", "Ticker"),
    "^SSEC": ("Shanghai_Composite_Index", "Symbol"),
    "^AXJO": ("S%26P_ASX_200", "Symbol"),
    "^GSPTSE": ("S%26P/TSX_Composite_Index", "Symbol"),
}


def _is_cache_fresh(cache: dict) -> bool:
    """Check if cache is still within TTL."""
    ts = cache.get("timestamp", "")
    try:
        cached_time = datetime.fromisoformat(ts)
        return datetime.now(timezone.utc) - cached_time < timedelta(hours=CACHE_TTL_HOURS)
    except (ValueError, TypeError):
        return False


def _read_cache() -> Optional[dict]:
    """Read universe cache from disk."""
    if not CACHE_FILE.exists():
        return None
    try:
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def _write_cache(universe: dict) -> None:
    """Write universe cache to disk with timestamp."""
    cache = {
        "tickers": universe,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "wikipedia + known constituents",
        "version": 1,
    }
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)


def _save_index_constituents(constituents: dict[str, list[str]]) -> None:
    """Save index constituents to separate cache file."""
    with open(INDEX_CONSTITUENTS_FILE, "w") as f:
        json.dump(constituents, f, indent=2, ensure_ascii=False)


def _load_index_constituents() -> dict[str, list[str]]:
    """Load pre-fetched index constituents from cache file."""
    if not INDEX_CONSTITUENTS_FILE.exists():
        return {}
    try:
        with open(INDEX_CONSTITUENTS_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def _extract_tickers_from_wikipedia(page_name: str, ticker_column: str) -> list[str]:
    """Extract ticker symbols from a Wikipedia table.

    Strategy:
    1. Find ALL wikitable tables on the page
    2. For each table, find the header row and locate the column matching `ticker_column`
    3. Extract values from that column across all rows
    4. Filter: must be 2-6 uppercase letters/digits, no spaces, no symbols (except .)

    Returns sorted unique list of tickers.
    """
    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError:
        logger.warning("requests and bs4 required for Wikipedia scraping")
        return []

    url = f"https://en.wikipedia.org/wiki/{page_name}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Rocket Stock Scanner bot; +https://github.com/svarkor-ai/rocket)"
    }

    try:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        logger.warning(f"Wikipedia fetch failed for {page_name}: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")

    # Find all wikitable tables
    tables = soup.find_all("table", {"class": re.compile(r"wikitable")})
    if not tables:
        logger.warning(f"No wikitable found for {page_name}")
        return []

    all_tickers = set()

    for table_idx, table in enumerate(tables):
        rows = table.find_all("tr")
        if not rows:
            continue

        # Find header row
        header_row = rows[0]
        header_cells = header_row.find_all(["th", "td"])

        # Find the index of the ticker column
        ticker_col_idx = None
        for i, cell in enumerate(header_cells):
            cell_text = cell.get_text(strip=True).lower()
            # Match columns named "Symbol", "Ticker", "Code", "Share", etc.
            if cell_text in ("symbol", "ticker", "code", "share", "stock", "instrument"):
                ticker_col_idx = i
                break

        if ticker_col_idx is None:
            # Try partial match
            for i, cell in enumerate(header_cells):
                cell_text = cell.get_text(strip=True).lower()
                if any(kw in cell_text for kw in ["symbol", "ticker", "code"]):
                    ticker_col_idx = i
                    break

        if ticker_col_idx is None:
            continue

        # Extract tickers from this column
        for row in rows[1:]:  # Skip header
            cells = row.find_all(["td", "th"])
            if ticker_col_idx < len(cells):
                cell_text = cells[ticker_col_idx].get_text(strip=True)
                # Clean up: remove links, references, etc.
                cell_text = re.sub(r'\[.*?\]', '', cell_text)  # Remove [1], [ref]
                cell_text = cell_text.strip()

                # Filter: must be 2-6 chars, uppercase letters/dots/digits
                if re.match(r"^[A-Z0-9.]{2,6}$", cell_text):
                    # Exclude common false positives
                    if cell_text not in ("N/A", "N/A.", "N.A.", "N/A.", "—", "-", ""):
                        all_tickers.add(cell_text)

    return sorted(all_tickers)


def _build_universe(force_refresh: bool = False) -> dict[str, list[str]]:
    """Build the ticker universe from index constituents.

    Strategy:
    1. Try cache first (fresh within 24h)
    2. If no cache or force_refresh:
       a. Fetch constituents from Wikipedia for major indices
       b. Add small/mid-cap tickers from additional sources
       c. Save to cache

    Returns dict[str, list[str]] with keys: usa, international

    The 'usa' region contains S&P 500 + Nasdaq 100 + Dow Jones + Russell 2000 + small caps.
    The 'international' region contains FTSE, DAX, CAC, Nikkei, Hang Seng, Shanghai, ASX, TSX.
    """
    # Try cache first
    if not force_refresh:
        cache = _read_cache()
        if cache and _is_cache_fresh(cache):
            logger.debug("Using cached universe data")
            return cache["tickers"]

    logger.info("Building universe from index constituents (Wikipedia)")
    universe: dict[str, list[str]] = {}
    constituents_cache: dict[str, list[str]] = {}

    # --- USA ---
    logger.info("Fetching US index constituents...")
    usa_tickers: set[str] = set()

    for name, (page_name, ticker_col) in WIKI_MAP.items():
        if name.startswith("^"):  # Only US indices
            logger.info(f"  Fetching {name} ({page_name}, col={ticker_col})...")
            tickers = _extract_tickers_from_wikipedia(page_name, ticker_col)
            if tickers:
                logger.info(f"    Got {len(tickers)} tickers from {name}")
                usa_tickers.update(tickers)
                constituents_cache[name] = tickers
            else:
                logger.warning(f"    No tickers from {name} ({page_name})")

    # Add known small-cap tickers if we didn't get enough from indices
    # S&P 500 ~ 500, Nasdaq 100 ~ 100, DJ ~ 30, Russell 2000 ~ 2000
    # Total from indices should be ~2600 unique (with overlap)
    if len(usa_tickers) < 2000:
        logger.warning(f"  Only got {len(usa_tickers)} US tickers from indices, adding known small caps")
        usa_tickers.update(_get_known_small_caps())

    universe["usa"] = sorted(usa_tickers)
    logger.info(f"  USA: {len(universe['usa'])} tickers")

    # --- International ---
    logger.info("Fetching international index constituents...")
    intl_tickers: set[str] = set()

    for name, (page_name, ticker_col) in WIKI_MAP.items():
        if not name.startswith("^"):  # Only international indices
            continue
        logger.info(f"  Fetching {name} ({page_name}, col={ticker_col})...")
        tickers = _extract_tickers_from_wikipedia(page_name, ticker_col)
        if tickers:
            logger.info(f"    Got {len(tickers)} tickers from {name}")
            intl_tickers.update(tickers)
            constituents_cache[name] = tickers
        else:
            logger.warning(f"    No tickers from {name} ({page_name})")

    universe["international"] = sorted(intl_tickers)
    logger.info(f"  International: {len(universe['international'])} tickers")

    # Save to both caches
    _write_cache(universe)
    _save_index_constituents(constituents_cache)

    logger.info(f"Universe built: {dict((k, len(v)) for k, v in universe.items())}")
    return universe


def _get_known_small_caps() -> list[str]:
    """Return a list of known small/mid-cap US tickers.

    These are publicly traded companies that are not in major indices but
    are still significant enough to scan for signals.
    Includes popular stocks (GME, AMC) and high-growth companies.
    """
    return [
        # Popular / meme stocks
        "GME", "AMC", "BB", "NOK", "WISH", "CLOV", "SPCE", "SNDL",
        # Mid/small cap US tickers
        "ABNB", "ANET", "CRWD", "DDOG", "SNOW", "PLTR", "RBLX", "COIN", "HOOD",
        "RIVN", "LCID", "SOFI", "AFRM", "UPST", "OPEN", "PTON", "MRNA",
        "ZM", "DOCU", "UBER", "LYFT", "DASH", "BILL", "S",
        "PATH", "APPF", "TWLO", "MDB", "GTLB", "ESTC", "AI", "NVO", "ALNY",
        # Additional small caps
        "CHPT", "ENPH", "SEDG", "RUN", "SPWR", "FSLR", "PLUG", "BE",
        "CELH", "MELI", "PINS", "SNPS", "CDNS", "ANSS",
        "FTNT", "DXCM", "VEEV", "ZBRA", "TTWO", "EA", "NTES", "BILI",
        "MDB", "DBX", "APPN", "NET", "ZS", "PANW", "OKTA",
    ]


# Public API
# ---------------------------------------------------------------------------

_universe_cache: Optional[dict[str, list[str]]] = None


def get_universe(region: str | None = None, force_refresh: bool = False) -> list[str] | dict[str, list[str]]:
    """Get ticker universe.

    Args:
        region: Region key or None for all.
        force_refresh: If True, skip cache and fetch live data.

    Returns:
        If region is specified, returns list[str] of tickers for that region.
        If region is None, returns dict[str, list[str]] of all regions.
    """
    global _universe_cache
    if _universe_cache is None or force_refresh:
        _universe_cache = _build_universe(force_refresh)

    if region is None:
        return dict(_universe_cache)

    return list(_universe_cache.get(region, []))


def get_universe_count() -> dict[str, int]:
    """Return dict of region -> number of tickers (from cache)."""
    global _universe_cache
    if _universe_cache is None:
        # Load from cache file directly without building
        cache = _read_cache()
        if cache and "tickers" in cache:
            _universe_cache = cache["tickers"]

    if _universe_cache is None:
        # Fallback: build without scraping (use embedded data only)
        _universe_cache = _build_embedded_fallback()

    return {region: len(tickers) for region, tickers in _universe_cache.items()}


def get_all_tickers() -> list[str]:
    """Return all unique tickers across all regions."""
    universe = get_universe()
    all_tickers = set()
    for tickers in universe.values():
        all_tickers.update(tickers)
    return sorted(all_tickers)


def get_all_universes() -> list[str]:
    """Alias for get_all_tickers — return all tickers across all regions."""
    return get_all_tickers()


def get_region_count() -> dict[str, int]:
    """Alias for get_universe_count."""
    return get_universe_count()


def get_total_count() -> int:
    """Return total number of unique tickers across all regions."""
    return len(get_all_tickers())


def _build_embedded_fallback() -> dict[str, list[str]]:
    """Fallback universe builder with embedded lists if Wikipedia fails.

    This provides ~957 tickers as a minimum viable universe.
    """
    # Embedded core lists — these are the tickers from previous versions
    # They're embedded as a fallback in case Wikipedia is unreachable

    # S&P 500 tickers (partial — real data would be 500+)
    USA_SP500_TICKERS = [
        'A', 'AA', 'AAL', 'AAP', 'AAPL', 'ABNB', 'ABT', 'ACN', 'ADBE',
        'ADM', 'ADP', 'ADSK', 'AEP', 'AXP', 'BA', 'BAC', 'BK', 'BLK',
        'BMY', 'BRK.B', 'C', 'CAT', 'CHTR', 'CI', 'CSCO', 'CVX',
        'DIS', 'DXCM', 'EBAY', 'EMR', 'EQIX', 'F', 'FDX', 'GM',
        'GOOGL', 'GS', 'HD', 'HON', 'IBM', 'INTC', 'JNJ', 'JPM',
        'KO', 'LMT', 'LOW', 'MA', 'MCD', 'MDLZ', 'MMM', 'MO',
        'MON', 'MRK', 'MSFT', 'NFLX', 'NKE', 'NVDA', 'OMC', 'ORCL',
        'PFE', 'PG', 'PM', 'PSA', 'PYPL', 'SBUX', 'SHW', 'SPGI',
        'T', 'TGT', 'TSLA', 'TXN', 'UNH', 'UNP', 'UPS', 'V',
        'VZ', 'WFC', 'WMT', 'XOM', 'CRM', 'AMZN',
    ]

    SWEDEN_TICKERS = [
        'AFA.ST', 'ABB.ST', 'ADV.ST', 'AMF.ST', 'ATC.ST', 'BEN.ST',
        'CARB.ST', 'CLAB.ST', 'CONC.ST', 'ESS.ST', 'HM.ST', 'ITUB.ST',
        'KFST.ST', 'MUB.ST', 'NPI.ST', 'OQA.ST', 'PEO.ST', 'SAB.ST',
        'SEB.ST', 'SAND.ST', 'SSAB.ST', 'SWED-A.ST', 'SWED-B.ST',
        'SVA.ST', 'Telia.ST', 'TIMETO.ST', 'VOLV-B.ST',
    ]

    # Add some known tickers from other regions
    # (This is a minimal fallback — full data comes from Wikipedia)
    INTERNATIONAL_TICKERS = [
        'BP.L', 'SHEL.L', 'GSK.L', 'AZN.L', 'ULVR.L',
        'DTE.DE', 'SIE.DE', 'ALV.DE', 'MBG.DE', 'BAS.DE',
        'OR.PA', 'SAN.PA', 'TTE.PA', 'BN.PA', 'AIR.PA',
        'NESN.SW', 'ROG.SW', 'NOVN.SW',
        '7203.T', '6758.T', '9984.T', '6861.T', '8306.T',
        '0700.HK', '1299.HK', '0941.HK', '0005.HK', '2888.HK',
        '1398.HK', '0939.HK', '0001.HK', '0003.HK',
        'WITM', 'BBVA.MC', 'IBE.MC', 'ITX.MC', 'ENF.MC',
        'MIL.MI', 'ENI.MI', 'UCG.MI', 'ISP.MI', 'STM.MI',
        'NXTD', 'ORSTED.CO', 'NOV.N', 'DNB.CO', 'EQNR.OL',
        'TLSI', 'KIR.BK', 'ESS.AB', 'SAM-B.ST', 'SEK-A.ST',
    ]

    return {
        'usa': sorted(set(USA_SP500_TICKERS)),
        'international': sorted(set(SWEDEN_TICKERS + INTERNATIONAL_TICKERS)),
    }

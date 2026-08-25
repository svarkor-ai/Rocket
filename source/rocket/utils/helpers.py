from datetime import datetime
from dateutil import parser as dateutil_parser


def normalize_ticker(ticker: str) -> str:
    """Normalize a ticker string to uppercase with dot separators."""
    return ticker.strip().upper().replace(' ', '.')


def get_region(ticker: str) -> str:
    """Infer region from ticker suffix."""
    ticker = ticker.upper()
    if ticker.endswith('.ST'):
        return 'smid'
    elif any(ticker.endswith(s) for s in ['.DE', '.FR', '.NL', '.BE', '.PT', '.ES', '.IT', '.PA', '.AS', '.BR', '.MC', '.MI', '.SW']):
        return 'eu'
    elif any(ticker.endswith(s) for s in ['.T', '.HK', '.KS', '.KQ', '.SZ', '.SS']):
        return 'asia'
    else:
        return 'us'


def parse_date(s) -> datetime:
    """Parse a date string or return datetime as-is."""
    if isinstance(s, datetime):
        return s
    return dateutil_parser.parse(str(s))


def format_score(score: float) -> str:
    """Format a numeric score to one decimal place."""
    return f"{score:.1f}"

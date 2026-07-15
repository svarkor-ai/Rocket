"""Quality filters — volume, price, market cap."""
from ..data.models import TickerInfo
from .models import FilterResult

MIN_AVG_VOLUME = 500_000      # $500k average daily volume
MIN_PRICE = 1.0               # $1 minimum price
MIN_MARKET_CAP = 50_000_000   # $50M market cap (or 0 to skip)


def apply_filters(
    ticker_info: TickerInfo,
    current_price: float = 0.0,
    min_volume: float = MIN_AVG_VOLUME,
    min_price: float = MIN_PRICE,
    min_market_cap: float = MIN_MARKET_CAP,
) -> FilterResult:
    """Apply quality filters to a ticker. Return FilterResult."""
    reasons = []
    ticker = ticker_info.ticker

    # Price filter
    price = current_price if current_price > 0 else 0.0
    if price < min_price:
        reasons.append(f"Price ${price:.2f} < ${min_price:.2f}")

    # Volume filter
    vol = ticker_info.avg_volume if ticker_info.avg_volume > 0 else 0.0
    if vol < min_volume:
        reasons.append(f"Volume {vol:.0f} < {min_volume:,}")

    # Market cap filter (skip if 0 — not available)
    cap = ticker_info.market_cap if ticker_info.market_cap > 0 else 0.0
    if min_market_cap > 0 and 0 < cap < min_market_cap:
        reasons.append(
            f"Market cap ${cap/1e6:.1f}M < ${min_market_cap/1e6:.0f}M"
        )

    return FilterResult(
        ticker=ticker,
        passed=len(reasons) == 0,
        reasons=reasons,
    )

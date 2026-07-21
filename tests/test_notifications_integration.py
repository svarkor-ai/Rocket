"""Test that Telegram notifications work with the new v2 pipeline."""
import sys
sys.path.insert(0, '/srv/svarkor/builds/rocket-stock-scanner')

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from rocket.data.models import TickerInfo, Region
from rocket.data.fundamentals import FundamentalData


# --- Helpers ---
def _make_mock_df():
    import pandas as pd
    import numpy as np
    dates = pd.date_range('2024-01-01', periods=250, freq='B')
    close = np.cumsum(np.random.randn(250) * 0.5) + 150
    return pd.DataFrame({
        'Open': close + np.random.randn(250) * 0.1,
        'High': close + abs(np.random.randn(250) * 0.2),
        'Low': close - abs(np.random.randn(250) * 0.2),
        'Close': close,
        'Volume': np.random.randint(1_000_000, 10_000_000, 250).astype(float),
        'Adj Close': close,
    })


def _make_mock_fd():
    from rocket.data.models import Region
    return FundamentalData(
        ticker='AAPL', region=Region.US,
        pe_ttm=25.0,
        pe_forward=22.0,
        roe=0.25,
        profit_margin=0.20,
        revenue_growth_ttm=0.10,
        debt_to_equity=1.5,
        current_ratio=1.2,
    )


# --- Tests ---
def test_notifications_module_imports():
    """Verify notification module can be imported and has all expected functions."""
    from rocket.telegram_bot.notifications import (
        CooldownManager,
        SignalDedupTracker,
        _score_emoji,
        send_signal_notification,
        send_notification_batch,
    )
    assert _score_emoji(0.5) in ("🟢", "🟣")
    assert _score_emoji(-0.5) in ("🔴", "🟠")


def test_coldown_manager():
    """CooldownManager works: record → is_cooldown → cooldown expired."""
    from rocket.telegram_bot.notifications import CooldownManager
    import time
    
    cm = CooldownManager(cooldown_seconds=0.1)  # short cooldown
    assert cm.is_cooldown('AAPL') is False
    
    cm.record('AAPL')
    assert cm.is_cooldown('AAPL') is True
    
    time.sleep(0.15)
    assert cm.is_cooldown('AAPL') is False  # expired


def test_signal_dedup_tracker():
    """SignalDedupTracker: same signal+score → skip; different → not skip."""
    from rocket.technical.models import Signal
    from rocket.telegram_bot.notifications import SignalDedupTracker
    
    dt = SignalDedupTracker()
    
    assert dt.should_skip('AAPL', Signal.BUY, 0.5) is False  # first
    dt.record('AAPL', Signal.BUY, 0.5)
    
    assert dt.should_skip('AAPL', Signal.BUY, 0.5) is True   # duplicate (same signal, same score)
    assert dt.should_skip('AAPL', Signal.BUY, 0.6) is False   # same signal, different score
    assert dt.should_skip('AAPL', Signal.SELL, 0.5) is False  # different signal
    
    # Record the different score
    dt.record('AAPL', Signal.BUY, 0.6)
    assert dt.should_skip('AAPL', Signal.BUY, 0.6) is True   # now this is duplicate


def test_score_emoji_mapping():
    """Score → emoji mapping covers all ranges."""
    from rocket.telegram_bot.notifications import _score_emoji
    
    assert _score_emoji(0.8) in ("🟣", "🟢")  # strong bullish
    assert _score_emoji(0.3) in ("🟢", "🟣")  # bullish  
    assert _score_emoji(0.0) == "⚪"          # neutral
    assert _score_emoji(-0.3) in ("🟠", "🔴")  # bearish
    assert _score_emoji(-0.8) in ("🟠", "🔴")  # strong bearish


def test_compute_rocket_score_with_fundamentals():
    """Pipeline produces fundamental_result when fundamentals provided."""
    import pandas as pd
    import numpy as np
    from rocket.scoring.rocket_score import compute_rocket_score
    
    df = _make_mock_df()
    fd = _make_mock_fd()
    ticker_info = TickerInfo(ticker='AAPL', region=Region.US)
    
    result = compute_rocket_score(
        df, ticker_info, current_price=150.0,
        fundamental_data=fd,
    )
    
    assert 'fundamental_result' in result
    assert result['fundamental_result'] is not None
    assert result['fundamental_result'].is_pass is True
    assert result['rocket_score'] != 0.0  # not rejected


def test_compute_rocket_score_rejected_low_fundamentals():
    """Pipeline rejects ticker when fundamentals fail filter + require_fundamentals=True."""
    import pandas as pd
    import numpy as np
    from rocket.scoring.rocket_score import compute_rocket_score
    
    df = _make_mock_df()
    fd = FundamentalData(
        ticker='BROKEN', region=Region.US,
        pe_ttm=200.0,  # terrible
        pe_forward=100.0,
        roe=-0.10,  # negative
        profit_margin=-0.05,  # loss
        revenue_growth_ttm=-0.20,  # shrinking
        debt_to_equity=10.0,  # highly leveraged
        current_ratio=0.3,
    )
    ticker_info = TickerInfo(ticker='BROKEN', region=Region.US)
    
    result = compute_rocket_score(
        df, ticker_info, current_price=10.0,
        fundamental_data=fd,
        require_fundamentals=True,
    )
    
    assert result['rocket_score'] == 0.0
    assert result['rocket_signal'].strength == "Neutral"
    assert "Rejected" in result['rocket_signal'].reason


def test_compute_rocket_score_without_fundamentals():
    """Pipeline works normally without fundamentals (backward compat)."""
    import pandas as pd
    import numpy as np
    from rocket.scoring.rocket_score import compute_rocket_score
    
    df = _make_mock_df()
    ticker_info = TickerInfo(ticker='AAPL', region=Region.US)
    
    result = compute_rocket_score(
        df, ticker_info, current_price=150.0,
    )
    
    assert result['rocket_score'] != 0.0  # should have a score
    assert 'fundamental_result' in result
    assert result['fundamental_result'] is None  # no fundamentals provided


def test_bot_handlers_import():
    """Telegram bot handlers can import without errors."""
    from rocket.telegram_bot.handlers import (
        start_command,
        subscribe_command,
        signal_command,
        scanall_command,
        help_command,
    )
    assert callable(start_command)
    assert callable(subscribe_command)
    assert callable(signal_command)


def test_bot_create_application():
    """Bot application can be created."""
    import os
    os.environ['SCAN_PRO_TELEGRAM_BOT_TOKEN'] = 'test:token'
    os.environ['SCAN_PRO_ADMIN_CHAT_ID'] = '12345'
    
    from rocket.telegram_bot.bot import create_application
    app = create_application()
    assert app is not None
    
    # Clean up
    del os.environ['SCAN_PRO_TELEGRAM_BOT_TOKEN']
    del os.environ['SCAN_PRO_ADMIN_CHAT_ID']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
"""TDD tests for the Rocket backtest engine (rocket/backtest/engine.py).

Prior state: 0 tests for the backtest engine (MC 987.5 / T1 "Testlucka").
This suite covers, in order of ascending coupling:

  1. BacktestResult metric properties (pure maths, no I/O)
  2. _execute_trade: commission, slippage, stop-loss, take-profit, position sizing
  3. strategy_momentum / strategy_top10 / strategy_threshold on synthetic data
  4. run_backtest with a provided scan_history (network/DB mocked away)
  5. walk-forward helper on a small synthetic series

No network and no signals.db are touched: fetch_prices and _get_db are
monkeypatched where a test would otherwise reach for them.
"""

import pytest

from rocket.backtest import engine


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures: controlled synthetic price series + scan history
# ─────────────────────────────────────────────────────────────────────────────

def _prices(start=1, n=10, base=100.0, step=1.0):
    """Monotone-ish daily closes. Day k implied by start+k.

    date string like '2024-01-01' ... price = base + k*step.
    """
    return [
        {"date": f"2024-01-{start+k:02d}", "close": base + k * step}
        for k in range(n)
    ]


@pytest.fixture
def flat_prices():
    """10 days, close = 100 always."""
    return [{"date": f"2024-01-{k+1:02d}", "close": 100.0} for k in range(10)]


@pytest.fixture
def rising_prices():
    """10 days, close = 100 + k."""
    return _prices(start=1, n=10)


# ═════════════════════════════════════════════════════════════════════════════
# 1. BacktestResult metric properties
# ═════════════════════════════════════════════════════════════════════════════

class TestBacktestResultMetrics:
    def test_total_return_compounds_multiplicatively(self):
        r = engine.BacktestResult("T", [
            {"return_pct": 10.0}, {"return_pct": -5.0}, {"return_pct": 20.0},
        ], [])
        # (1.10 * 0.95 * 1.20) - 1 = 0.254
        assert r.total_return == pytest.approx(25.4)

    def test_total_return_empty_trades_is_zero(self):
        r = engine.BacktestResult("T", [], [])
        assert r.total_return == 0.0

    def test_win_rate(self):
        r = engine.BacktestResult("T", [
            {"return_pct": 10.0}, {"return_pct": -5.0}, {"return_pct": 20.0},
        ], [])
        assert r.win_rate == pytest.approx(2 / 3 * 100)

    def test_win_rate_empty_trades_is_zero(self):
        assert engine.BacktestResult("T", [], []).win_rate == 0.0

    def test_max_drawdown(self):
        r = engine.BacktestResult("T", [
            {"return_pct": 10.0}, {"return_pct": -50.0},
        ], [])
        # cum: 1.0 -> 1.1 -> 0.55 ; peak 1.1, dd (1.1-0.55)/1.1 = 50%
        assert r.max_drawdown == pytest.approx(50.0)

    def test_max_drawdown_empty_trades_is_zero(self):
        assert engine.BacktestResult("T", [], []).max_drawdown == 0.0

    def test_sharpe_needs_two_trades(self):
        assert engine.BacktestResult("T", [{"return_pct": 5.0}], []).sharpe_ratio == 0.0

    def test_sharpe_zero_std_returns_zero(self):
        r = engine.BacktestResult("T", [
            {"return_pct": 5.0}, {"return_pct": 5.0},
        ], [])
        assert r.sharpe_ratio == 0.0

    def test_sharpe_positive_for_positive_returns(self):
        r = engine.BacktestResult("T", [
            {"return_pct": 10.0}, {"return_pct": 20.0}, {"return_pct": 30.0},
        ], [])
        assert r.sharpe_ratio > 0

    def test_annualized_return_uses_trading_days(self):
        r = engine.BacktestResult("T", [
            {"return_pct": 10.0},
        ], [], capital=1.0, position_size_pct=1.0, trading_days=63)
        # one +10% trade; years = 63/252 = 0.25 so 1/years = 4
        # -> (1.10 ** 4 - 1) * 100 = 46.41
        assert r.annualized_return == pytest.approx((1.10 ** 4 - 1) * 100)

    def test_annualized_return_zero_without_trading_days(self):
        r = engine.BacktestResult("T", [{"return_pct": 10.0}], [], trading_days=0)
        assert r.annualized_return == 0.0

    def test_sortino_uses_downside_deviation(self):
        # returns +10, +20, -5 -> mean 25/3 = 8.3333...
        # downside = [-5], downside_dev = 5
        r = engine.BacktestResult("T", [
            {"return_pct": 10.0}, {"return_pct": 20.0}, {"return_pct": -5.0},
        ], [])
        assert r.sortino_ratio == pytest.approx((25 / 3) / 5.0)

    def test_sortino_no_losses_is_zero(self):
        r = engine.BacktestResult("T", [
            {"return_pct": 10.0}, {"return_pct": 20.0},
        ], [])
        assert r.sortino_ratio == 0.0

    def test_avg_holding_days(self):
        r = engine.BacktestResult("T", [
            {"return_pct": 1.0, "holding_days": 3},
            {"return_pct": 1.0, "holding_days": 5},
        ], [])
        assert r.avg_holding_days == pytest.approx(4.0)

    def test_avg_holding_days_empty_is_zero(self):
        assert engine.BacktestResult("T", [], []).avg_holding_days == 0.0


# ═════════════════════════════════════════════════════════════════════════════
# 2. _execute_trade: costs, stops, position sizing
# ═════════════════════════════════════════════════════════════════════════════

class TestExecuteTrade:
    def test_no_cost_return_is_price_move(self):
        t = engine._execute_trade("d1", 100.0, "d4", 110.0,
                                  0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 3)
        assert t["return_pct"] == pytest.approx(10.0)
        assert t["raw_return_pct"] == pytest.approx(10.0)

    def test_commission_and_slippage_lower_return(self):
        t = engine._execute_trade("d1", 100.0, "d4", 110.0,
                                  0.001, 0.0005, 0.0005, 0.0, 0.0, 1.0, 3)
        # effective entry 100.05, effective exit 109.945
        assert t["return_pct"] == pytest.approx((109.945 - 100.05) / 100.05 * 100)

    def test_stop_loss_forces_exit_at_stop(self):
        t = engine._execute_trade("d1", 100.0, "d4", 90.0,
                                  0.0, 0.0, 0.0, 5.0, 0.0, 1.0, 3)
        assert t["exit_price"] == pytest.approx(95.0)
        assert t["return_pct"] == pytest.approx(-5.0)

    def test_take_profit_forces_exit_at_tp(self):
        t = engine._execute_trade("d1", 100.0, "d4", 120.0,
                                  0.0, 0.0, 0.0, 0.0, 10.0, 1.0, 3)
        assert t["exit_price"] == pytest.approx(110.0)
        assert t["return_pct"] == pytest.approx(10.0)

    def test_position_size_scales_return(self):
        t_half = engine._execute_trade("d1", 100.0, "d4", 110.0,
                                       0.0, 0.0, 0.0, 0.0, 0.0, 0.5, 3)
        t_full = engine._execute_trade("d1", 100.0, "d4", 110.0,
                                       0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 3)
        assert t_half["return_pct"] == pytest.approx(t_full["return_pct"] * 0.5)

    def test_holding_days_recorded(self):
        t = engine._execute_trade("d1", 100.0, "d4", 110.0,
                                  0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 7)
        assert t["holding_days"] == 7


# ═════════════════════════════════════════════════════════════════════════════
# 3. Strategies on synthetic data
# ═════════════════════════════════════════════════════════════════════════════

class TestStrategyMomentum:
    def test_buy_signal_opens_3day_hold(self, rising_prices):
        scan = [{"date": "2024-01-01", "signal": "BUY", "score": 0.8, "reason": "x"}]
        res = engine.strategy_momentum("T", rising_prices, scan, 30)
        assert len(res.trades) == 1
        t = res.trades[0]
        # entry day1 close=100, hold 3 -> exit day4 close=103
        assert t["entry"] == "2024-01-01"
        assert t["exit"] == "2024-01-04"
        assert t["holding_days"] == 3

    def test_momentum_ignores_low_scores(self, rising_prices):
        scan = [{"date": "2024-01-01", "signal": "BUY", "score": 0.2, "reason": "x"}]
        res = engine.strategy_momentum("T", rising_prices, scan, 30)
        assert len(res.trades) == 0

    def test_momentum_records_evaluated_signals(self, rising_prices):
        scan = [{"date": "2024-01-01", "signal": "BUY", "score": 0.8}]
        res = engine.strategy_momentum("T", rising_prices, scan, 30)
        assert len(res.signals) == 1
        assert res.signals[0]["score"] == 0.8

    def test_momentum_skips_exit_beyond_series(self, rising_prices):
        # signal on the last day: entry_idx=9, exit_idx=12 out of range -> no trade
        scan = [{"date": "2024-01-10", "signal": "BUY", "score": 0.9}]
        res = engine.strategy_momentum("T", rising_prices, scan, 30)
        assert len(res.trades) == 0


class TestStrategyTop10:
    def test_opens_single_position_and_closes_after_hold(self, rising_prices):
        scan = [{"date": "2024-01-01", "signal": "BUY", "score": 0.9}]
        res = engine.strategy_top10("T", rising_prices, scan, 30)
        assert len(res.trades) == 1
        t = res.trades[0]
        assert t["entry"] == "2024-01-01"
        assert t["holding_days"] == 5

    def test_no_signal_day_produces_no_trade(self, flat_prices):
        res = engine.strategy_top10("T", flat_prices, [], 30)
        assert len(res.trades) == 0

    def test_top10_limits_to_top_10_but_one_portfolio_position(self, rising_prices):
        # 12 signals same day, but only ONE portfolio position opened
        scan = [
            {"date": "2024-01-01", "signal": "BUY", "score": float(i)}
            for i in range(1, 13)
        ]
        res = engine.strategy_top10("T", rising_prices, scan, 30)
        # one position opened (len(open_positions)==0 guard), held 5 days, then
        # no further entries on later dates -> exactly 1 trade
        assert len(res.trades) == 1


class TestStrategyThreshold:
    def test_buys_above_threshold_holds_until_exit(self, rising_prices):
        scan = [{"date": "2024-01-01", "signal": "BUY", "score": 0.8}]
        res = engine.strategy_threshold(
            "T", rising_prices, scan, 30,
            buy_threshold=0.3, sell_threshold=-0.3, hold_days=2,
        )
        assert len(res.trades) == 1
        t = res.trades[0]
        assert t["entry"] == "2024-01-01"
        assert t["holding_days"] == 2

    def test_below_buy_threshold_no_entry(self, rising_prices):
        scan = [{"date": "2024-01-01", "signal": "BUY", "score": 0.1}]
        res = engine.strategy_threshold(
            "T", rising_prices, scan, 30,
            buy_threshold=0.3, sell_threshold=-0.3, hold_days=2,
        )
        assert len(res.trades) == 0

    def test_threshold_reports_signals_evaluated(self, rising_prices):
        scan = [{"date": "2024-01-01", "signal": "BUY", "score": 0.8}]
        res = engine.strategy_threshold(
            "T", rising_prices, scan, 30,
            buy_threshold=0.3, sell_threshold=-0.3, hold_days=2,
        )
        assert len(res.signals) == 1


# ═════════════════════════════════════════════════════════════════════════════
# 4. run_backtest with provided scan_history (no network / no DB)
# ═════════════════════════════════════════════════════════════════════════════

class TestRunBacktest:
    def test_run_backtest_uses_provided_scan_history(self, rising_prices, monkeypatch):
        monkeypatch.setattr(engine, "fetch_prices", lambda ticker, days: rising_prices)
        scan = [{"date": "2024-01-01", "signal": "BUY", "score": 0.8}]
        res = engine.run_backtest("T", 30, strategy="threshold",
                                  scan_history=scan, hold_days=2)
        assert len(res.trades) == 1
        assert res.ticker == "T"

    def test_run_backtest_unknown_strategy_raises(self, rising_prices, monkeypatch):
        monkeypatch.setattr(engine, "fetch_prices", lambda ticker, days: rising_prices)
        with pytest.raises(ValueError):
            engine.run_backtest("T", 30, strategy="nope", scan_history=[])

    def test_run_backtest_empty_prices_returns_empty(self, monkeypatch):
        monkeypatch.setattr(engine, "fetch_prices", lambda ticker, days: [])
        res = engine.run_backtest("T", 30, strategy="threshold", scan_history=[])
        assert res.total_return == 0.0
        assert res.trades == []

    def test_run_backtest_momentum_path(self, rising_prices, monkeypatch):
        monkeypatch.setattr(engine, "fetch_prices", lambda ticker, days: rising_prices)
        scan = [{"date": "2024-01-01", "signal": "BUY", "score": 0.8}]
        res = engine.run_backtest("T", 30, strategy="momentum", scan_history=scan)
        assert len(res.trades) == 1

    def test_walk_forward_pools_trades(self, monkeypatch):
        # 10-day series, train=3 test=2 -> contiguous windows after idx 3.
        prices = _prices(start=1, n=10, step=1.0)
        monkeypatch.setattr(engine, "fetch_prices", lambda ticker, days: prices)
        scan = [{"date": d["date"], "signal": "BUY", "score": 0.9}
                for d in prices]
        res = engine.run_backtest(
            "T", 30, strategy="momentum", scan_history=scan,
            walk_forward=True, walk_train_days=3, walk_test_days=2,
        )
        # BUY signals every day -> pooled trades across windows > 0
        assert len(res.trades) > 0
        assert len(res.signals) > 0


# ═════════════════════════════════════════════════════════════════════════════
# 5. STRATEGIES registry
# ═════════════════════════════════════════════════════════════════════════════

class TestStrategiesRegistry:
    def test_registry_lists_three_strategies(self):
        assert set(engine.STRATEGIES.keys()) == {"momentum", "top10", "threshold"}

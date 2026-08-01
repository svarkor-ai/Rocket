"""Meme stock backtesting engine.

Backtests meme stock patterns to identify recurring signals
and measure historical performance of meme stock trading strategies.
"""
import logging

import pandas as pd
from typing import List, Dict
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class BacktestTrade:
    """A single trade in the backtest."""
    ticker: str
    entry_date: str
    entry_price: float
    exit_date: str
    exit_price: float
    shares: int
    pnl: float
    pnl_pct: float
    holding_days: int
    signal: str  # entry signal type


@dataclass
class BacktestResult:
    """Results from a meme stock backtest run."""
    ticker: str
    strategy: str
    trades: List[BacktestTrade]
    total_return_pct: float
    total_trades: int
    win_rate: float
    avg_win_pct: float
    avg_loss_pct: float
    max_drawdown_pct: float
    sharpe_ratio: float
    buy_and_hold_return_pct: float
    metrics: Dict = field(default_factory=dict)


class MemeBacktester:
    """Backtests meme stock trading strategies.
    
    Strategies:
    - volume_spike: Enter on volume > 2x average, exit after 5 days
    - short_squeeze: Enter on gap up > 5% with volume spike, exit after 10 days
    - social_surge: Enter on high social mentions, exit after 7 days
    - combined: Enter when momentum + meme score exceed thresholds
    """

    def __init__(self, initial_capital: float = 100000.0):
        self.initial_capital = initial_capital

    def run(self, ticker: str, df: 'pd.DataFrame',
            start_date: str = None, end_date: str = None,
            strategy: str = 'combined') -> BacktestResult:
        """Run a backtest for a single ticker.
        
        Args:
            ticker: Stock ticker
            df: OHLCV DataFrame (sorted by date ascending)
            start_date: Optional start date (YYYY-MM-DD)
            end_date: Optional end date (YYYY-MM-DD)
            strategy: One of 'volume_spike', 'short_squeeze', 'social_surge', 'combined'
        """
        if df is None or len(df) < 50:
            return BacktestResult(
                ticker=ticker, strategy=strategy,
                trades=[], total_return_pct=0, total_trades=0,
                win_rate=0, avg_win_pct=0, avg_loss_pct=0,
                max_drawdown_pct=0, sharpe_ratio=0,
                buy_and_hold_return_pct=0
            )

        # Filter by date range if specified
        if start_date:
            df = df[df.index >= start_date]
        if end_date:
            df = df[df.index <= end_date]

        if len(df) < 30:
            return BacktestResult(
                ticker=ticker, strategy=strategy,
                trades=[], total_return_pct=0, total_trades=0,
                win_rate=0, avg_win_pct=0, avg_loss_pct=0,
                max_drawdown_pct=0, sharpe_ratio=0,
                buy_and_hold_return_pct=0
            )

        # Generate signals and execute trades
        trades = []

        if strategy in ('volume_spike', 'combined'):
            trades.extend(self._volume_spike_trades(ticker, df))

        if strategy in ('short_squeeze', 'combined'):
            trades.extend(self._short_squeeze_trades(ticker, df))

        if strategy in ('social_surge', 'combined'):
            trades.extend(self._social_surge_trades(ticker, df))

        if not trades:
            trades = self._volume_spike_trades(ticker, df)  # fallback

        # Calculate metrics
        total_trades = len(trades)
        winners = [t for t in trades if t.pnl > 0]
        losers = [t for t in trades if t.pnl <= 0]

        win_rate = len(winners) / total_trades if total_trades > 0 else 0
        avg_win = sum(t.pnl_pct for t in winners) / len(winners) if winners else 0
        avg_loss = sum(t.pnl_pct for t in losers) / len(losers) if losers else 0

        # Max drawdown
        equity = self.initial_capital
        peak = self.initial_capital
        max_dd = 0
        for t in trades:
            equity += t.pnl
            if equity > peak:
                peak = equity
            dd = (peak - equity) / peak * 100 if peak > 0 else 0
            max_dd = max(max_dd, dd)

        # Sharpe ratio (annualized, simplified)
        returns = [t.pnl_pct for t in trades]
        if returns and len(returns) > 1:
            mean_ret = sum(returns) / len(returns)
            std_ret = (sum((r - mean_ret) ** 2 for r in returns) / (len(returns) - 1)) ** 0.5
            sharpe = (mean_ret / std_ret * (252 ** 0.5)) if std_ret > 0 else 0
        else:
            sharpe = 0

        # Buy and hold return
        buy_hold = (df.iloc[-1]['close'] - df.iloc[0]['close']) / df.iloc[0]['close'] * 100

        total_return = sum(t.pnl for t in trades) / self.initial_capital * 100

        return BacktestResult(
            ticker=ticker,
            strategy=strategy,
            trades=trades,
            total_return_pct=round(total_return, 2),
            total_trades=total_trades,
            win_rate=round(win_rate, 3),
            avg_win_pct=round(avg_win, 2),
            avg_loss_pct=round(avg_loss, 2),
            max_drawdown_pct=round(max_dd, 2),
            sharpe_ratio=round(sharpe, 2),
            buy_and_hold_return_pct=round(buy_hold, 2),
            metrics={
                'winners': len(winners),
                'losers': len(losers),
                'initial_capital': self.initial_capital,
            },
        )

    def _volume_spike_trades(self, ticker: str, df: 'pd.DataFrame') -> List[BacktestTrade]:
        """Generate volume spike trades."""
        trades = []
        volume = df['volume'].astype(float)
        close = df['close'].astype(float)

        # 20-day average volume
        avg_vol = volume.rolling(20).mean()

        position = None
        entry_idx = None

        for i in range(20, len(df)):
            vol_ratio = volume.iloc[i] / avg_vol.iloc[i] if avg_vol.iloc[i] > 0 else 0

            if vol_ratio > 2.5 and position is None:
                # Entry
                entry_price = close.iloc[i]
                entry_date = str(df.index[i].date())
                shares = max(1, int(10000 / entry_price))  # $10k position
                position = entry_price
                entry_idx = i

            elif position is not None:
                # Exit conditions
                holding_days = i - entry_idx

                if holding_days >= 10:  # Max hold 10 days
                    exit_price = close.iloc[i]
                    pnl = (exit_price - position) * shares
                    pnl_pct = (exit_price - position) / position * 100

                    trades.append(BacktestTrade(
                        ticker=ticker,
                        entry_date=entry_date,
                        entry_price=round(position, 2),
                        exit_date=str(df.index[i].date()),
                        exit_price=round(exit_price, 2),
                        shares=shares,
                        pnl=round(pnl, 2),
                        pnl_pct=round(pnl_pct, 2),
                        holding_days=holding_days,
                        signal='volume_spike'
                    ))

                    position = None
                    entry_idx = None

        return trades

    def _short_squeeze_trades(self, ticker: str, df: 'pd.DataFrame') -> List[BacktestTrade]:
        """Generate short squeeze trades."""
        trades = []
        close = df['close'].astype(float)
        volume = df['volume'].astype(float)
        df['high'].astype(float)

        avg_vol = volume.rolling(20).mean()

        position = None
        entry_price = None
        entry_date = None
        entry_idx = None

        for i in range(20, len(df)):
            vol_ratio = volume.iloc[i] / avg_vol.iloc[i] if avg_vol.iloc[i] > 0 else 0

            # Gap up > 5% with volume > 2x
            if i > 0:
                gap_pct = (close.iloc[i] - close.iloc[i-1]) / close.iloc[i-1] * 100
            else:
                gap_pct = 0

            if gap_pct > 5 and vol_ratio > 2 and position is None:
                entry_price = close.iloc[i]
                entry_date = str(df.index[i].date())
                shares = max(1, int(10000 / entry_price))
                position = entry_price
                entry_idx = i

            elif position is not None:
                holding_days = i - entry_idx

                if holding_days >= 10 or (gap_pct > 10 and i > entry_idx + 1):
                    exit_price = close.iloc[i]
                    pnl = (exit_price - position) * shares
                    pnl_pct = (exit_price - position) / position * 100

                    trades.append(BacktestTrade(
                        ticker=ticker,
                        entry_date=entry_date,
                        entry_price=round(position, 2),
                        exit_date=str(df.index[i].date()),
                        exit_price=round(exit_price, 2),
                        shares=shares,
                        pnl=round(pnl, 2),
                        pnl_pct=round(pnl_pct, 2),
                        holding_days=holding_days,
                        signal='short_squeeze'
                    ))

                    position = None
                    entry_idx = None

        return trades

    def _social_surge_trades(self, ticker: str, df: 'pd.DataFrame') -> List[BacktestTrade]:
        """Generate social surge trades (simulated social data)."""
        # In practice, this would use real social mention counts
        # For now, simulate based on volume spikes as proxy
        return self._volume_spike_trades(ticker, df)

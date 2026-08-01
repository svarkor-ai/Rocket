"""Backtest result models."""
from dataclasses import dataclass, field
from typing import List
from datetime import datetime


@dataclass
class Trade:
    """A single trade."""
    date: datetime
    ticker: str
    action: str            # "BUY" or "SELL"
    price: float
    quantity: int = 1
    commission: float = 0.0


@dataclass
class MetricsDict:
    """Dictionary-style metrics for a backtest."""
    total_return: float = 0.0
    annualized_return: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown: float = 0.0
    calmar_ratio: float = 0.0
    win_rate: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0


@dataclass
class BacktestResult:
    """Complete backtest output."""
    strategy: str
    ticker: str
    trades: List[Trade] = field(default_factory=list)
    equity_curve: List[float] = field(default_factory=list)
    dates: List[datetime] = field(default_factory=list)
    metrics: MetricsDict = field(default_factory=MetricsDict)
    initial_capital: float = 100000.0
    final_value: float = 0.0
    benchmark_curve: List[float] = field(default_factory=list)

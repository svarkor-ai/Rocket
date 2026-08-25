"""Calculate backtest performance metrics."""
import numpy as np
import pandas as pd
from typing import List
from .models import Trade, MetricsDict


def calculate_metrics(
    trades: List[Trade],
    equity_curve: pd.Series,
    risk_free_rate: float = 0.02,
) -> MetricsDict:
    """Compute standard backtest metrics from trades and equity curve.

    Parameters
    ----------
    trades : List of Trade objects
    equity_curve : Series of equity values indexed by datetime
    risk_free_rate : Annual risk-free rate for Sharpe calculation
    """
    total_trades = len(trades)
    wins = 0
    losses = 0
    total_profit = 0.0
    total_loss = 0.0
    win_amounts = []
    loss_amounts = []
    consecutive_wins = 0
    consecutive_losses = 0
    max_consecutive_wins = 0
    max_consecutive_losses = 0

    # Calculate individual trade PnL (BUY-SELL pairs)
    open_trades = {}
    for trade in trades:
        if trade.action == "BUY":
            open_trades[trade.date] = {
                "price": trade.price,
                "quantity": trade.quantity,
            }
        elif trade.action == "SELL" and trade.date in open_trades:
            entry = open_trades.pop(trade.date)
            pnl = (trade.price - entry["price"]) * entry["quantity"]
            if pnl > 0:
                wins += 1
                total_profit += pnl
                win_amounts.append(pnl)
                consecutive_wins += 1
                consecutive_losses = 0
                max_consecutive_wins = max(max_consecutive_wins, consecutive_wins)
            else:
                losses += 1
                total_loss += abs(pnl)
                loss_amounts.append(abs(pnl))
                consecutive_losses += 1
                consecutive_wins = 0
                max_consecutive_losses = max(max_consecutive_losses, consecutive_losses)

   # Equity curve metrics
    if not isinstance(equity_curve, pd.Series):
        equity_curve = pd.Series(equity_curve)
    returns = equity_curve.pct_change().dropna()
    if len(returns) > 1:
        daily_returns = returns.values
        daily_rf = risk_free_rate / 252

        # Total return
        total_return = (equity_curve.iloc[-1] / equity_curve.iloc[0]) - 1

        # Annualized return
        n_days = (equity_curve.index[-1] - equity_curve.index[0]).days
        if n_days > 0:
            annualized_return = (1 + total_return) ** (252 / n_days) - 1
        else:
            annualized_return = 0.0

        # Sharpe ratio
        excess_returns = daily_returns - daily_rf
        sharpe = (
            np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252)
            if np.std(excess_returns) > 0 else 0.0
        )

        # Sortino ratio
        downside_returns = daily_returns[daily_returns < daily_rf] - daily_rf
        if len(downside_returns) > 0 and np.std(downside_returns) > 0:
            sortino = (
                np.mean(downside_returns) / np.std(downside_returns) * np.sqrt(252)
            )
        else:
            sortino = 0.0

        # Max drawdown
        peak = equity_curve.cummax()
        drawdown = (equity_curve - peak) / peak
        max_drawdown = abs(drawdown.min())

        # Calmar ratio
        calmar = annualized_return / max_drawdown if max_drawdown > 0 else 0.0
    else:
        total_return = 0.0
        annualized_return = 0.0
        sharpe = 0.0
        sortino = 0.0
        max_drawdown = 0.0
        calmar = 0.0

    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0.0
    avg_win = np.mean(win_amounts) if win_amounts else 0.0
    avg_loss = np.mean(loss_amounts) if loss_amounts else 0.0
    profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')

    return MetricsDict(
        total_return=round(float(total_return), 4),
        annualized_return=round(float(annualized_return), 4),
        sharpe_ratio=round(float(sharpe), 4),
        sortino_ratio=round(float(sortino), 4),
        max_drawdown=round(float(max_drawdown), 4),
        calmar_ratio=round(float(calmar), 4),
        win_rate=round(float(win_rate), 2),
        total_trades=total_trades,
        winning_trades=wins,
        losing_trades=losses,
        avg_win=round(float(avg_win), 2),
        avg_loss=round(float(avg_loss), 2),
        profit_factor=round(float(profit_factor), 4),
        max_consecutive_wins=max_consecutive_wins,
        max_consecutive_losses=max_consecutive_losses,
    )

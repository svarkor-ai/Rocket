"""Event-driven backtest engine."""
import numpy as np
import pandas as pd
from datetime import datetime
from typing import List, Optional
from .models import Trade, BacktestResult, MetricsDict
from .strategy import BaseStrategy
from .metrics import calculate_metrics


def run_backtest(
    df: pd.DataFrame,
    strategy: BaseStrategy,
    initial_capital: float = 100000.0,
    commission_pct: float = 0.001,
    benchmark_df: Optional[pd.DataFrame] = None,
) -> BacktestResult:
    """Run an event-driven backtest on OHLCV data.

    Parameters
    ----------
    df : DataFrame with OHLCV data (close, high, low, volume, date index)
    strategy : BaseStrategy subclass implementing generate_signals()
    initial_capital : Starting cash
    commission_pct : Commission per trade as a fraction
    benchmark_df : Optional DataFrame for benchmark comparison
    """
    trades: List[Trade] = []
    cash = initial_capital
    position = 0
    position_price = 0.0
    equity_curve = [initial_capital]
    dates = []

    for i in range(len(df)):
        row = df.iloc[i]
        date = row.name if hasattr(row.name, 'strftime') else datetime.now()
        close = row.get('close', row.get('Close', None))
        high = row.get('high', row.get('High', close))
        low = row.get('low', row.get('Low', close))
        volume = row.get('volume', row.get('Volume', 0))

        # Generate signals
        signals = strategy.generate_signals(df, i)

        if isinstance(signals, list):
            for sig in signals:
                if sig.get('action') == 'BUY' and position == 0:
                    # Buy
                    qty = int(cash * sig.get('pct', 0.99) / close)
                    if qty > 0:
                        cost = qty * close * (1 + commission_pct)
                        cash -= cost
                        position = qty
                        position_price = close
                        trades.append(Trade(
                            date=date, ticker="SYNTH", action="BUY",
                            price=close, quantity=qty,
                            commission=qty * close * commission_pct,
                        ))

                elif sig.get('action') == 'SELL' and position > 0:
                    # Sell — use position (not qty which is from BUY branch)
                    sell_qty = min(sig.get('qty', position), position)
                    revenue = sell_qty * close * (1 - commission_pct)
                    cash += revenue
                    trades.append(Trade(
                        date=date, ticker="SYNTH", action="SELL",
                        price=close, quantity=sell_qty,
                        commission=sell_qty * close * commission_pct,
                    ))
                    position -= sell_qty
                    position_price = 0.0
                    if position == 0:
                        break
        else:
            sig = signals
            if sig and sig.get('action') == 'BUY' and position == 0:
                qty = int(cash * sig.get('pct', 0.99) / close)
                if qty > 0:
                    cost = qty * close * (1 + commission_pct)
                    cash -= cost
                    position = qty
                    position_price = close
                    trades.append(Trade(
                        date=date, ticker="SYNTH", action="BUY",
                        price=close, quantity=qty,
                        commission=qty * close * commission_pct,
                    ))
            elif sig and sig.get('action') == 'SELL' and position > 0:
                sell_qty = min(sig.get('qty', position), position)
                revenue = sell_qty * close * (1 - commission_pct)
                cash += revenue
                trades.append(Trade(
                    date=date, ticker="SYNTH", action="SELL",
                    price=close, quantity=sell_qty,
                    commission=sell_qty * close * commission_pct,
                ))
                position -= sell_qty
                position_price = 0.0
                if position == 0:
                    break

        # Track equity — only append dates for each candle, equity has initial_capital + len(df) entries
        equity = cash + position * close
        equity_curve.append(equity)
        dates.append(date)

    # Ensure equity_curve and dates are same length (equity has len+1 due to initial value)
    equity_curve = equity_curve[:len(dates)]

    # Compute metrics
    equity_series = pd.Series(equity_curve, index=dates)
    metrics = calculate_metrics(trades, equity_series)

    final_value = equity_curve[-1] if equity_curve else initial_capital

    return BacktestResult(
        strategy=strategy.name,
        ticker="SYNTH",
        trades=trades,
        equity_curve=equity_curve,
        dates=dates,
        metrics=metrics,
        initial_capital=initial_capital,
        final_value=final_value,
    )

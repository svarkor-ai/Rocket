"""Parameter sensitivity analysis for strategies."""
import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Dict, List, Any, Callable
from .engine import run_backtest
from .strategy import BaseStrategy
from .models import BacktestResult, MetricsDict


@dataclass
class SensitivityResult:
    """Results from parameter sweep."""
    strategy_name: str
    param_grid: dict
    results: List[Dict[str, Any]] = field(default_factory=list)
    best_params: dict = field(default_factory=dict)
    best_sharpe: float = 0.0
    best_return: float = 0.0


def run_sensitivity(
    df: pd.DataFrame,
    strategy: BaseStrategy,
    param_grid: Dict[str, List[Any]],
    initial_capital: float = 100000.0,
) -> SensitivityResult:
    """Run backtest across all parameter combinations.

    Parameters
    ----------
    df : OHLCV DataFrame
    strategy : Strategy class with configurable parameters
    param_grid : Dict of parameter_name → list of values to try
    initial_capital : Starting capital

    Returns
    -------
    SensitivityResult with all combinations and best parameters.
    """
    results = []
    best_sharpe = float('-inf')
    best_params = {}
    best_return = float('-inf')

    # Generate all combinations
    keys = list(param_grid.keys())
    values = list(param_grid.values())

    def _combo(idx, current_params):
        nonlocal best_sharpe, best_params, best_return
        if idx == len(keys):
            # Run backtest with current params
            try:
                # Create strategy instance with current params
                strat = strategy(**{k: current_params[k] for k in keys})
                bt = run_backtest(
                    df, strat, initial_capital=initial_capital
                )
                m = bt.metrics
                entry = {
                    **current_params,
                    "sharpe": m.sharpe_ratio,
                    "return": m.total_return,
                    "drawdown": m.max_drawdown,
                    "win_rate": m.win_rate,
                    "trades": m.total_trades,
                }
                results.append(entry)

                if m.sharpe_ratio > best_sharpe:
                    best_sharpe = m.sharpe_ratio
                    best_params = dict(current_params)
                    best_return = m.total_return
            except Exception as e:
                print(f"Combo {current_params} failed: {e}")
            return

        key = keys[idx]
        for val in values[idx]:
            current_params[key] = val
            _combo(idx + 1, current_params)

    _combo(0, {})

    return SensitivityResult(
        strategy_name=strategy.name,
        param_grid=param_grid,
        results=results,
        best_params=best_params,
        best_sharpe=round(float(best_sharpe), 4),
        best_return=round(float(best_return), 4),
    )

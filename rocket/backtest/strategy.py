"""Built-in trading strategies for backtesting."""
import numpy as np
import pandas as pd
from abc import ABC, abstractmethod
from typing import Optional, Dict, List


class BaseStrategy(ABC):
    """Base class for backtest strategies."""
    name = "Base"

    @abstractmethod
    def generate_signals(
        self, df: pd.DataFrame, idx: int
    ) -> Optional[Dict]:
        """Generate a signal dict or None at index idx."""
        ...


class BuyHoldStrategy(BaseStrategy):
    """Simple buy-and-hold strategy."""
    name = "Buy & Hold"

    def generate_signals(self, df: pd.DataFrame, idx: int) -> Optional[Dict]:
        if idx == 0:
            return {"action": "BUY", "pct": 0.99}
        return {"action": "HOLD"}


class EMACrossoverStrategy(BaseStrategy):
    """EMA 9/21 crossover strategy."""
    name = "EMA Crossover 9/21"

    def __init__(self, fast: int = 9, slow: int = 21):
        self.fast = fast
        self.slow = slow

    def generate_signals(self, df: pd.DataFrame, idx: int) -> Optional[Dict]:
        if idx < self.slow + 5:
            return {"action": "HOLD"}

        close = df['close']
        ema_fast = close.ewm(span=self.fast, adjust=False).mean()
        ema_slow = close.ewm(span=self.slow, adjust=False).mean()

        if idx >= len(ema_fast) or idx >= len(ema_slow):
            return None

        cur_fast = ema_fast.iloc[idx]
        cur_slow = ema_slow.iloc[idx]
        prev_fast = ema_fast.iloc[idx - 1] if idx > 0 else cur_fast
        prev_slow = ema_slow.iloc[idx - 1] if idx > 0 else cur_slow

        if prev_fast <= prev_slow and cur_fast > cur_slow:
            return {"action": "BUY", "pct": 0.95}
        elif prev_fast >= prev_slow and cur_fast < cur_slow:
            return {"action": "SELL", "pct": 1.0}
        return None


class RSIBasedStrategy(BaseStrategy):
    """RSI mean-reversion strategy: buy RSI<30, sell RSI>70."""
    name = "RSI Reversal"

    def __init__(self, period: int = 14, buy_threshold: float = 30,
                 sell_threshold: float = 70):
        self.period = period
        self.buy_t = buy_threshold
        self.sell_t = sell_threshold

    def generate_signals(self, df: pd.DataFrame, idx: int) -> Optional[Dict]:
        if idx < self.period:
            return {"action": "HOLD"}

        close = df['close']
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(self.period).mean()
        loss = (-delta.clip(upper=0)).rolling(self.period).mean()
        rs = gain / loss.replace(0, np.finfo(float).eps)
        rsi = 100 - (100 / (1 + rs))

        if idx >= len(rsi):
            return None

        rsi_val = rsi.iloc[idx]

        if rsi_val < self.buy_t:
            return {"action": "BUY", "pct": 0.95}
        elif rsi_val > self.sell_t:
            return {"action": "SELL", "pct": 1.0}
        return None


class RocketComboStrategy(BaseStrategy):
    """Combined strategy: RSI + EMA crossover + volume confirmation."""
    name = "Rocket Combo"

    def __init__(self, rsi_period: int = 14, rsi_buy: float = 35,
                 rsi_sell: float = 65, ema_fast: int = 9, ema_slow: int = 21):
        self.rsi_period = rsi_period
        self.rsi_buy = rsi_buy
        self.rsi_sell = rsi_sell
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow

    def generate_signals(self, df: pd.DataFrame, idx: int) -> Optional[Dict]:
        if idx < max(self.rsi_period, self.ema_slow) + 5:
            return {"action": "HOLD"}

        close = df['close']
        high = df.get('high', close)
        low = df.get('low', close)

        # RSI
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(self.rsi_period).mean()
        loss = (-delta.clip(upper=0)).rolling(self.rsi_period).mean()
        rs = gain / loss.replace(0, np.finfo(float).eps)
        rsi = 100 - (100 / (1 + rs))

        # EMAs
        ema_fast = close.ewm(span=self.ema_fast, adjust=False).mean()
        ema_slow = close.ewm(span=self.ema_slow, adjust=False).mean()

        if idx >= len(rsi) or idx >= len(ema_fast):
            return None

        rsi_val = rsi.iloc[idx]
        ef = ema_fast.iloc[idx]
        es = ema_slow.iloc[idx]
        efp = ema_fast.iloc[idx - 1] if idx > 0 else ef
        esp = ema_slow.iloc[idx - 1] if idx > 0 else es

        # Buy conditions (need at least 2 of 3)
        buy_signals = 0
        if rsi_val < self.rsi_buy:
            buy_signals += 1
        if efp <= esp and ef > es:
            buy_signals += 1
        if idx >= 2:
            vol_avg = df['volume'].iloc[idx - self.rsi_period:idx].mean()
            if df['volume'].iloc[idx] > vol_avg:
                buy_signals += 1

        # Sell conditions
        sell_signals = 0
        if rsi_val > self.rsi_sell:
            sell_signals += 1
        if efp >= esp and ef < es:
            sell_signals += 1

        if buy_signals >= 2:
            return {"action": "BUY", "pct": 0.95}
        elif sell_signals >= 1:
            return {"action": "SELL", "pct": 1.0}
        return None

"""Momentum + Social Score engine for meme stock analysis.

Computes a combined score from:
- Technical momentum indicators (price, volume, volatility)
- Social sentiment (Reddit, news)
- Meme stock pattern detection

Supports backtesting of meme stock patterns.
"""
import logging
from typing import List, Dict, Optional, TypedDict
from dataclasses import dataclass, field
import numpy as np

logger = logging.getLogger(__name__)


# ── Data structures ──────────────────────────────────────────────────────

class MemeStockPattern(TypedDict, total=False):
    """Detected meme stock pattern."""
    ticker: str
    pattern: str  # "meme_rally", "short_squeeze", "social_surge", "volume_spike"
    score: float  # 0-100
    confidence: float  # 0-1
    details: str


@dataclass
class MemeStockScore:
    """Combined meme stock score for a single ticker."""
    ticker: str
    momentum_score: float       # 0-100
    social_score: float         # 0-100
    meme_score: float           # 0-100
    combined_score: float       # weighted combined
    pattern: str = ""           # dominant pattern
    details: Dict = field(default_factory=dict)
    
    def to_dict(self):
        return {
            'ticker': self.ticker,
            'momentum_score': round(self.momentum_score, 1),
            'social_score': round(self.social_score, 1),
            'meme_score': round(self.meme_score, 1),
            'combined_score': round(self.combined_score, 1),
            'pattern': self.pattern,
            'details': self.details,
        }


# ── Momentum scoring ────────────────────────────────────────────────────

class MomentumScorer:
    """Computes momentum scores from price/volume data.
    
    Input: OHLCV DataFrame with columns:
        ['open', 'high', 'low', 'close', 'volume']
    """
    
    def __init__(self, short_window: int = 5, long_window: int = 20):
        self.short_window = short_window
        self.long_window = long_window
    
    def compute(self, df: 'pd.DataFrame') -> float:
        """Compute momentum score from OHLCV DataFrame.
        
        Returns 0-100 score.
        """
        if df is None or len(df) < self.long_window:
            return 50.0  # neutral if insufficient data
        
        try:
            import pandas as pd
            close = df['close'].astype(float)
            volume = df['volume'].astype(float)
            
            # 1. Price momentum (40%)
            price_momentum = self._price_momentum(close)
            
            # 2. Volume momentum (30%)
            vol_momentum = self._volume_momentum(volume, close)
            
            # 3. Volatility-adjusted return (30%)
            vol_return = self._volatility_adjusted_return(close, volume)
            
            score = (price_momentum * 0.40 +
                     vol_momentum * 0.30 +
                     vol_return * 0.30)
            
            return float(np.clip(score, 0, 100))
        
        except Exception as e:
            logger.warning(f"Momentum scoring failed: {e}")
            return 50.0
    
    def _price_momentum(self, close: 'pd.Series') -> float:
        """Price momentum component (0-100)."""
        short_ma = close.rolling(self.short_window).mean().iloc[-1]
        long_ma = close.rolling(self.long_window).mean().iloc[-1]
        
        if long_ma == 0:
            return 50.0
        
        # Price above/below moving averages
        price_pos = close.iloc[-1] / long_ma  # ratio > 1 = bullish
        
        # Short-term trend
        short_trend = (close.iloc[-1] - close.iloc[-self.short_window]) / close.iloc[-self.short_window] * 100
        
        # Crossover signal
        crossover = (short_ma - long_ma) / long_ma * 100
        
        # Combine: higher = bullish
        score = (
            min(max(price_pos * 50 - 25, 0), 100) +  # price vs long MA
            min(max(short_trend * 20, -50), 50) +     # short trend
            min(max(crossover * 10, -50), 50)         # MA crossover
        )
        
        return (score + 100) / 2  # normalize to 0-100
    
    def _volume_momentum(self, volume: 'pd.Series', close: 'pd.Series') -> float:
        """Volume momentum component (0-100)."""
        avg_volume = volume.rolling(self.long_window).mean().iloc[-1]
        current_volume = volume.iloc[-1]
        
        if avg_volume == 0:
            return 50.0
        
        volume_ratio = current_volume / avg_volume
        
        # Volume spike = bullish momentum
        if volume_ratio > 3:
            score = 90
        elif volume_ratio > 2:
            score = 75
        elif volume_ratio > 1.5:
            score = 60
        elif volume_ratio > 1:
            score = 45
        else:
            score = 30
        
        # Adjust for price direction
        price_change = (close.iloc[-1] - close.iloc[-self.short_window]) / close.iloc[-self.short_window]
        if price_change > 0 and volume_ratio > 1.5:
            score += 10  # rising prices + rising volume = strong bullish
        elif price_change < 0 and volume_ratio > 1.5:
            score -= 10  # falling prices + rising volume = strong bearish
        
        return min(max(score, 0), 100)
    
    def _volatility_adjusted_return(self, close: 'pd.Series', volume: 'pd.Series') -> float:
        """Volatility-adjusted return (0-100)."""
        returns = close.pct_change().dropna()
        if len(returns) < 10:
            return 50.0
        
        avg_return = returns.mean()
        volatility = returns.std()
        
        if volatility == 0:
            return 50.0
        
        # Sharpe-like ratio
        sharpe = avg_return / volatility
        
        # Normalize to 0-100
        score = 50 + sharpe * 25
        
        return min(max(score, 0), 100)


# ── Meme pattern detection ──────────────────────────────────────────────

class MemePatternDetector:
    """Detects meme stock patterns from price/volume data."""
    
    # Classic meme stock tickers
    KNOWN_MEME = {'GME', 'AMC', 'BB', 'BBBY', 'CLOV', 'AMC', 'WISH', 'SPCE', 'RIVN', 'SNDL', 'NOK'}
    
    def detect(self, ticker: str, df: 'pd.DataFrame',
               social_mentions: int = 0) -> MemeStockPattern:
        """Detect if a ticker matches a meme stock pattern.
        
        Returns pattern info with score and confidence.
        """
        if df is None or len(df) < 20:
            return {
                'ticker': ticker,
                'pattern': 'insufficient_data',
                'score': 0,
                'confidence': 0,
                'details': 'Not enough data'
            }
        
        close = df['close'].astype(float)
        volume = df['volume'].astype(float)
        
        patterns = []
        
        # 1. Known meme stock
        if ticker.upper() in self.KNOWN_MEME:
            patterns.append(('known_meme', 50, 0.9, 'Known meme stock'))
        
        # 2. Short squeeze pattern
        squeeze = self._detect_short_squeeze(close, volume)
        if squeeze['score'] > 30:
            patterns.append(squeeze)
        
        # 3. Social surge pattern
        if social_mentions > 5:
            social_score = min(social_mentions * 10, 100)
            patterns.append((
                'social_surge',
                social_score,
                min(0.3 + social_mentions * 0.05, 0.9),
                f'{social_mentions} social mentions'
            ))
        
        # 4. Volume spike
        vol_spike = self._detect_volume_spike(volume, close)
        if vol_spike['score'] > 30:
            patterns.append(vol_spike)
        
        if not patterns:
            return {
                'ticker': ticker,
                'pattern': 'none',
                'score': 0,
                'confidence': 0,
                'details': 'No meme patterns detected'
            }
        
        # Return highest scoring pattern
        best = max(patterns, key=lambda x: x[1])
        return {
            'ticker': ticker,
            'pattern': best[0],
            'score': min(best[1], 100),
            'confidence': best[2],
            'details': best[3],
        }
    
    def _detect_short_squeeze(self, close: 'pd.Series',
                               volume: 'pd.Series') -> MemeStockPattern:
        """Detect short squeeze indicators."""
        avg_vol = volume.rolling(20).mean().iloc[-1]
        current_vol = volume.iloc[-1]
        
        # Price gap up + massive volume
        yesterday_close = close.iloc[-2] if len(close) > 1 else close.iloc[-1]
        gap_pct = (close.iloc[-1] - yesterday_close) / yesterday_close * 100 if yesterday_close > 0 else 0
        
        vol_ratio = current_vol / avg_vol if avg_vol > 0 else 0
        
        # Squeeze score: gap up + volume spike
        score = 0
        confidence = 0.5
        
        if gap_pct > 5:
            score += 30
            confidence += 0.15
        elif gap_pct > 2:
            score += 15
            confidence += 0.1
        
        if vol_ratio > 3:
            score += 40
            confidence += 0.15
        elif vol_ratio > 2:
            score += 25
            confidence += 0.1
        elif vol_ratio > 1.5:
            score += 10
        
        # Multiple day squeeze
        if gap_pct > 10 and vol_ratio > 2:
            score += 20
        
        return {
            'ticker': '',
            'pattern': 'short_squeeze',
            'score': min(score, 100),
            'confidence': min(confidence, 0.95),
            'details': f'Gap up {gap_pct:.1f}% with {vol_ratio:.1f}x volume',
        }
    
    def _detect_volume_spike(self, volume: 'pd.Series',
                              close: 'pd.Series') -> MemeStockPattern:
        """Detect unusual volume spikes."""
        avg_vol = volume.rolling(20).mean().iloc[-1]
        current_vol = volume.iloc[-1]
        
        if avg_vol == 0:
            return {'ticker': '', 'pattern': 'none', 'score': 0, 'confidence': 0, 'details': ''}
        
        ratio = current_vol / avg_ratio
        vol_ratio = current_vol / avg_vol
        
        # Score based on volume spike magnitude
        if vol_ratio > 5:
            score = 85
        elif vol_ratio > 3:
            score = 65
        elif vol_ratio > 2:
            score = 45
        else:
            score = 20
        
        # Price direction confirmation
        price_change = (close.iloc[-1] - close.iloc[-5]) / close.iloc[-5] * 100 if len(close) >= 5 else 0
        if price_change > 0 and vol_ratio > 2:
            score += 10
        
        return {
            'ticker': '',
            'pattern': 'volume_spike',
            'score': min(score, 100),
            'confidence': min(0.3 + vol_ratio * 0.1, 0.8),
            'details': f'Volume {vol_ratio:.1f}x average, price change {price_change:.1f}%',
        }


# ── Combined scoring ────────────────────────────────────────────────────

class MomentumSocialScorer:
    """Combined momentum + social + meme scoring engine."""
    
    # Weights
    MOMENTUM_WEIGHT = 0.40
    SOCIAL_WEIGHT = 0.30
    MEME_WEIGHT = 0.30
    
    def __init__(self):
        self.momentum_scorer = MomentumScorer()
        self.pattern_detector = MemePatternDetector()
    
    def score(self, ticker: str,
              df: 'pd.DataFrame',
              social_mentions: int = 0,
              social_score: float = 50.0) -> MemeStockScore:
        """Compute combined meme stock score.
        
        Args:
            ticker: Stock ticker symbol
            df: OHLCV DataFrame
            social_mentions: Number of social media mentions
            social_score: Social sentiment score (0-100)
        
        Returns:
            MemeStockScore with all components.
        """
        # 1. Momentum score
        momentum = self.momentum_scorer.compute(df)
        
        # 2. Social score (normalize from -1..1 to 0-100)
        if social_score < 0:
            social = 50 + social_score * 50  # -1..1 → 0..50
        else:
            social = social_score  # 0..1 → 0..100
        
        # 3. Meme pattern score
        pattern = self.pattern_detector.detect(ticker, df, social_mentions)
        meme = pattern['score']
        
        # 4. Combined score
        combined = (
            momentum * self.MOMENTUM_WEIGHT +
            social * self.SOCIAL_WEIGHT +
            meme * self.MEME_WEIGHT
        )
        
        # Determine dominant pattern
        scores = {
            'momentum': momentum,
            'social': social,
            'meme': meme,
        }
        dominant = max(scores, key=scores.get)
        
        if dominant == 'meme' and pattern['pattern'] != 'none':
            dominant_pattern = pattern['pattern']
        else:
            dominant_pattern = f"{dominant}_driven"
        
        return MemeStockScore(
            ticker=ticker,
            momentum_score=momentum,
            social_score=social,
            meme_score=meme,
            combined_score=combined,
            pattern=dominant_pattern,
            details={
                'momentum_weight': self.MOMENTUM_WEIGHT,
                'social_weight': self.SOCIAL_WEIGHT,
                'meme_weight': self.MEME_WEIGHT,
                'pattern_details': pattern,
                'social_mentions': social_mentions,
            },
        )
    
    def rank(self, scores: List[MemeStockScore],
             top_n: int = 50) -> List[MemeStockScore]:
        """Rank scores by combined score (descending)."""
        return sorted(scores, key=lambda s: s.combined_score, reverse=True)[:top_n]

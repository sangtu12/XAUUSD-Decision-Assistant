import logging
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

class FeatureEngine:
    @staticmethod
    def calculate_ema(series: pd.Series, period: int) -> pd.Series:
        return series.ewm(span=period, adjust=False).mean()

    @staticmethod
    def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
        delta = series.diff()
        gain = (delta.where(delta > 0, 0.0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0.0)).rolling(window=period).mean()
        rs = gain / (loss + 1e-9)
        return 100 - (100 / (1 + rs))

    @staticmethod
    def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
        high_low = df["high"] - df["low"]
        high_close = (df["high"] - df["close"].shift()).abs()
        low_close = (df["low"] - df["close"].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        return tr.rolling(window=period).mean()

    @classmethod
    def detect_swings(cls, df: pd.DataFrame, lookback: int = 3) -> Dict[str, Any]:
        """Detect Swing Highs and Swing Lows using fractal lookback.
        A bar at index i is a Swing High if high[i] > high[i-k..i-1] and high[i] > high[i+1..i+k].
        """
        swing_highs = []
        swing_lows = []
        highs = df["high"].values
        lows = df["low"].values
        times = df["timestamp_utc"].values
        n = len(df)

        for i in range(lookback, n - lookback):
            # Check high
            if all(highs[i] > highs[i - k] for k in range(1, lookback + 1)) and \
               all(highs[i] >= highs[i + k] for k in range(1, lookback + 1)):
                swing_highs.append({"index": i, "price": float(highs[i]), "time": str(times[i])})

            # Check low
            if all(lows[i] < lows[i - k] for k in range(1, lookback + 1)) and \
               all(lows[i] <= lows[i + k] for k in range(1, lookback + 1)):
                swing_lows.append({"index": i, "price": float(lows[i]), "time": str(times[i])})

        return {"swing_highs": swing_highs, "swing_lows": swing_lows}

    @classmethod
    def detect_fvg(cls, df: pd.DataFrame, min_gap_cents: float = 0.5) -> List[Dict[str, Any]]:
        """Fair Value Gap (FVG):
        Bullish FVG: Low of candle i > High of candle i-2. Gap = Low[i] - High[i-2]
        Bearish FVG: High of candle i < Low of candle i-2. Gap = Low[i-2] - High[i]
        """
        fvgs = []
        lows = df["low"].values
        highs = df["high"].values
        times = df["timestamp_utc"].values

        for i in range(2, len(df)):
            # Bullish FVG
            if lows[i] > highs[i - 2]:
                gap = lows[i] - highs[i - 2]
                if gap >= min_gap_cents:
                    fvgs.append({
                        "type": "BULLISH_FVG",
                        "top": float(lows[i]),
                        "bottom": float(highs[i - 2]),
                        "gap": float(gap),
                        "time": str(times[i])
                    })
            # Bearish FVG
            elif highs[i] < lows[i - 2]:
                gap = lows[i - 2] - highs[i]
                if gap >= min_gap_cents:
                    fvgs.append({
                        "type": "BEARISH_FVG",
                        "top": float(lows[i - 2]),
                        "bottom": float(highs[i]),
                        "gap": float(gap),
                        "time": str(times[i])
                    })
        return fvgs

    @classmethod
    def compute_all_features(cls, df: pd.DataFrame) -> pd.DataFrame:
        """Compute TA, swings, FVG, and append as columns/metadata."""
        res = df.copy()
        res["ema_20"] = cls.calculate_ema(res["close"], 20)
        res["ema_50"] = cls.calculate_ema(res["close"], 50)
        res["ema_200"] = cls.calculate_ema(res["close"], 200)
        res["rsi_14"] = cls.calculate_rsi(res["close"], 14)
        res["atr_14"] = cls.calculate_atr(res, 14)
        return res

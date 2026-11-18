import logging
from typing import Dict, Any
import pandas as pd

logger = logging.getLogger(__name__)

class RegimeDetector:
    @staticmethod
    def classify(df: pd.DataFrame) -> Dict[str, Any]:
        """Classifies direction regime and volatility regime independently.
        Requirements:
        - Direction: BULLISH_TREND, BEARISH_TREND, RANGING, TRANSITION
        - Volatility: LOW, NORMAL, HIGH, EXTREME
        """
        if df is None or len(df) < 50:
            return {
                "trend_regime": "TRANSITION",
                "volatility_regime": "NORMAL",
                "evidence": {"reason": "INSUFFICIENT_DATA"}
            }

        last_row = df.iloc[-2]  # Use last closed candle (index -2) to prevent bar 0 lookahead
        close = last_row["close"]
        ema_20 = last_row.get("ema_20", close)
        ema_50 = last_row.get("ema_50", close)
        ema_200 = last_row.get("ema_200", close)
        atr_14 = last_row.get("atr_14", 1.0)

        # 1. Direction classification
        if close > ema_20 > ema_50 > ema_200:
            trend = "BULLISH_TREND"
        elif close < ema_20 < ema_50 < ema_200:
            trend = "BEARISH_TREND"
        elif abs(ema_20 - ema_50) / ema_50 < 0.001:
            trend = "RANGING"
        else:
            trend = "TRANSITION"

        # 2. Volatility classification based on ATR relative to historical median ATR
        atr_series = df["atr_14"].dropna()
        if len(atr_series) >= 20:
            atr_median = atr_series.median()
            atr_ratio = atr_14 / (atr_median + 1e-6)
            if atr_ratio < 0.7:
                volatility = "LOW"
            elif atr_ratio <= 1.4:
                volatility = "NORMAL"
            elif atr_ratio <= 2.2:
                volatility = "HIGH"
            else:
                volatility = "EXTREME"
        else:
            volatility = "NORMAL"
            atr_ratio = 1.0

        return {
            "trend_regime": trend,
            "volatility_regime": volatility,
            "evidence": {
                "close": float(close),
                "ema_20": float(ema_20),
                "ema_50": float(ema_50),
                "ema_200": float(ema_200),
                "atr_14": float(atr_14),
                "atr_ratio": round(float(atr_ratio), 2)
            }
        }

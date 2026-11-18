import logging
from typing import Dict, Any, List, Optional
import pandas as pd
from engine.strategies.base import BaseStrategy
from engine.feature_engine import FeatureEngine

logger = logging.getLogger(__name__)

class LiquiditySweepStrategy(BaseStrategy):
    def __init__(self):
        super().__init__(name="LiquiditySweepReversal", version="0.3")

    def evaluate(
        self,
        timeframe_dfs: Dict[str, pd.DataFrame],
        regime: Dict[str, Any],
        symbol_info: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        candidates = []
        df_m15 = timeframe_dfs.get("M15")
        df_m5 = timeframe_dfs.get("M5")

        if df_m15 is None or df_m5 is None:
            return candidates
        if len(df_m15) < 30 or len(df_m5) < 30:
            return candidates

        # 1. Detect M15 Swings
        swings = FeatureEngine.detect_swings(df_m15, lookback=3)
        swing_highs = swings["swing_highs"]
        swing_lows = swings["swing_lows"]

        if not swing_highs and not swing_lows:
            return candidates

        m5_last = df_m5.iloc[-2]
        m5_high = float(m5_last["high"])
        m5_low = float(m5_last["low"])
        m5_close = float(m5_last["close"])
        m5_atr = float(m5_last.get("atr_14", 1.5))
        current_bid = symbol_info.get("bid", m5_close)
        current_ask = symbol_info.get("ask", m5_close)

        # 2. Check for Bullish Liquidity Sweep (Sweep of recent Swing Low + reclaim)
        if swing_lows:
            recent_low = swing_lows[-1]["price"]
            # Price breached recent swing low, but closed back above it (sweep & reclaim)
            if m5_low < recent_low and m5_close > recent_low:
                sl = m5_low - (m5_atr * 0.3)
                risk = current_ask - sl
                if risk > 0:
                    tp = current_ask + (risk * 2.0)
                    candidates.append({
                        "strategy": self.name,
                        "direction": "BUY",
                        "fingerprint": f"SWEEP_BUY_{round(recent_low, 1)}_{m5_last['timestamp_utc'].strftime('%Y%m%d%H%M')}",
                        "market_plan": {
                            "entry_type": "MARKET",
                            "reference_price": current_ask,
                            "entry_price": current_ask,
                            "stop_loss": sl,
                            "take_profit": tp,
                            "risk_reward": 2.0,
                            "invalidation_price": sl
                        },
                        "limit_plan": {
                            "entry_type": "BUY_LIMIT",
                            "entry_price": round(recent_low, 2),
                            "stop_loss": sl,
                            "take_profit": tp,
                            "risk_reward": round((tp - recent_low) / (recent_low - sl), 2) if (recent_low - sl) > 0 else 0,
                            "invalidation_price": sl
                        },
                        "rationale": f"Bullish Liquidity Sweep: M15 swing low {recent_low} swept on M5 and reclaimed."
                    })

        # 3. Check for Bearish Liquidity Sweep (Sweep of recent Swing High + rejection)
        if swing_highs:
            recent_high = swing_highs[-1]["price"]
            if m5_high > recent_high and m5_close < recent_high:
                sl = m5_high + (m5_atr * 0.3)
                risk = sl - current_bid
                if risk > 0:
                    tp = current_bid - (risk * 2.0)
                    candidates.append({
                        "strategy": self.name,
                        "direction": "SELL",
                        "fingerprint": f"SWEEP_SELL_{round(recent_high, 1)}_{m5_last['timestamp_utc'].strftime('%Y%m%d%H%M')}",
                        "market_plan": {
                            "entry_type": "MARKET",
                            "reference_price": current_bid,
                            "entry_price": current_bid,
                            "stop_loss": sl,
                            "take_profit": tp,
                            "risk_reward": 2.0,
                            "invalidation_price": sl
                        },
                        "limit_plan": {
                            "entry_type": "SELL_LIMIT",
                            "entry_price": round(recent_high, 2),
                            "stop_loss": sl,
                            "take_profit": tp,
                            "risk_reward": round((recent_high - tp) / (sl - recent_high), 2) if (sl - recent_high) > 0 else 0,
                            "invalidation_price": sl
                        },
                        "rationale": f"Bearish Liquidity Sweep: M15 swing high {recent_high} swept on M5 and rejected."
                    })

        return candidates

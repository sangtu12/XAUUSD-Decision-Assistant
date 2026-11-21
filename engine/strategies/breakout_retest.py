import logging
from typing import Dict, Any, List, Optional
import pandas as pd
from engine.strategies.base import BaseStrategy
from engine.feature_engine import FeatureEngine

logger = logging.getLogger(__name__)

class BreakoutRetestStrategy(BaseStrategy):
    def __init__(self):
        super().__init__(name="BreakoutRetest", version="0.3")

    def evaluate(
        self,
        timeframe_dfs: Dict[str, pd.DataFrame],
        regime: Dict[str, Any],
        symbol_info: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        candidates = []
        df_h1 = timeframe_dfs.get("H1")
        df_m15 = timeframe_dfs.get("M15")

        if df_h1 is None or df_m15 is None:
            return candidates
        if len(df_h1) < 30 or len(df_m15) < 30:
            return candidates

        # 1. Identify Key S/R from H1 Swings (Institutional lookback=5)
        h1_swings = FeatureEngine.detect_swings(df_h1, lookback=5)
        h1_highs = [s["price"] for s in h1_swings["swing_highs"]]
        h1_lows = [s["price"] for s in h1_swings["swing_lows"]]

        m15_last = df_m15.iloc[-2]
        m15_prev = df_m15.iloc[-3]
        m15_close = float(m15_last["close"])
        m15_open = float(m15_last["open"])
        m15_low = float(m15_last["low"])
        m15_high = float(m15_last["high"])
        m15_atr = float(m15_last.get("atr_14", 2.0))
        current_bid = symbol_info.get("bid", m15_close)
        current_ask = symbol_info.get("ask", m15_close)

        # 2. Bullish Breakout & Retest of Resistance
        if h1_highs:
            recent_res = h1_highs[-1]
            # Breakout occurred on prev candle, retest on current candle holding as support
            if float(m15_prev["close"]) > recent_res and abs(m15_low - recent_res) <= m15_atr * 0.4 and m15_close > recent_res and m15_close >= m15_open:
                sl = recent_res - (m15_atr * 0.7)
                risk = current_ask - sl
                if risk > 0:
                    tp1 = current_ask + (risk * 2.0)
                    tp2 = current_ask + (risk * 3.5)
                    tp3 = current_ask + (risk * 5.0)
                    candidates.append({
                        "strategy": self.name,
                        "direction": "BUY",
                        "fingerprint": f"BR_BUY_{round(recent_res, 1)}_{m15_last['timestamp_utc'].strftime('%Y%m%d%H%M')}",
                        "market_plan": {
                            "entry_type": "MARKET",
                            "reference_price": current_ask,
                            "entry_price": current_ask,
                            "stop_loss": sl,
                            "take_profit": tp1,
                            "take_profit_2": tp2,
                            "take_profit_3": tp3,
                            "risk_reward": 2.0,
                            "invalidation_price": sl
                        },
                        "limit_plan": {
                            "entry_type": "BUY_LIMIT",
                            "entry_price": round(recent_res, 2),
                            "stop_loss": sl,
                            "take_profit": tp1,
                            "take_profit_2": tp2,
                            "take_profit_3": tp3,
                            "risk_reward": round((tp1 - recent_res) / (recent_res - sl), 2) if (recent_res - sl) > 0 else 0,
                            "invalidation_price": sl
                        },
                        "rationale": f"H1 Resistance {round(recent_res, 2)} broken with displacement, M15 retested and held as support."
                    })

        # 3. Bearish Breakout & Retest of Support
        if h1_lows:
            recent_sup = h1_lows[-1]
            if float(m15_prev["close"]) < recent_sup and abs(m15_high - recent_sup) <= m15_atr * 0.4 and m15_close < recent_sup and m15_close <= m15_open:
                sl = recent_sup + (m15_atr * 0.7)
                risk = sl - current_bid
                if risk > 0:
                    tp1 = current_bid - (risk * 2.0)
                    tp2 = current_bid - (risk * 3.5)
                    tp3 = current_bid - (risk * 5.0)
                    candidates.append({
                        "strategy": self.name,
                        "direction": "SELL",
                        "fingerprint": f"BR_SELL_{round(recent_sup, 1)}_{m15_last['timestamp_utc'].strftime('%Y%m%d%H%M')}",
                        "market_plan": {
                            "entry_type": "MARKET",
                            "reference_price": current_bid,
                            "entry_price": current_bid,
                            "stop_loss": sl,
                            "take_profit": tp1,
                            "take_profit_2": tp2,
                            "take_profit_3": tp3,
                            "risk_reward": 2.0,
                            "invalidation_price": sl
                        },
                        "limit_plan": {
                            "entry_type": "SELL_LIMIT",
                            "entry_price": round(recent_sup, 2),
                            "stop_loss": sl,
                            "take_profit": tp1,
                            "take_profit_2": tp2,
                            "take_profit_3": tp3,
                            "risk_reward": round((recent_sup - tp1) / (sl - recent_sup), 2) if (sl - recent_sup) > 0 else 0,
                            "invalidation_price": sl
                        },
                        "rationale": f"H1 Support {round(recent_sup, 2)} broken with displacement, M15 retested and held as resistance."
                    })

        return candidates

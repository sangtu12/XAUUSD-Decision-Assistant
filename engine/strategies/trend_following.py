import logging
from typing import Dict, Any, List, Optional
from decimal import Decimal
import pandas as pd
from engine.strategies.base import BaseStrategy

logger = logging.getLogger(__name__)

class TrendFollowingStrategy(BaseStrategy):
    def __init__(self):
        super().__init__(name="TrendFollowing", version="0.3")

    def evaluate(
        self,
        timeframe_dfs: Dict[str, pd.DataFrame],
        regime: Dict[str, Any],
        symbol_info: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        candidates = []
        df_h1 = timeframe_dfs.get("H1")
        df_m15 = timeframe_dfs.get("M15")
        df_m5 = timeframe_dfs.get("M5")

        if df_h1 is None or df_m15 is None or df_m5 is None:
            return candidates
        if len(df_h1) < 50 or len(df_m15) < 50 or len(df_m5) < 50:
            return candidates

        # 1. Macro Bias on H1/H4
        h1_last = df_h1.iloc[-2]  # last closed bar
        h1_bias = "BUY" if h1_last["close"] > h1_last.get("ema_50", h1_last["close"]) else "SELL"

        # 2. M15 Pullback to EMA 20/50 zone
        m15_last = df_m15.iloc[-2]
        m15_close = float(m15_last["close"])
        m15_ema20 = float(m15_last.get("ema_20", m15_close))
        m15_ema50 = float(m15_last.get("ema_50", m15_close))
        m15_atr = float(m15_last.get("atr_14", 2.0))

        # Check if M15 pulled back near EMA 20-50
        in_pullback = False
        if h1_bias == "BUY" and (m15_close <= m15_ema20 or abs(m15_close - m15_ema20) < m15_atr * 0.5):
            in_pullback = True
        elif h1_bias == "SELL" and (m15_close >= m15_ema20 or abs(m15_close - m15_ema20) < m15_atr * 0.5):
            in_pullback = True

        if not in_pullback:
            return candidates

        # 3. M5 Trigger / Reversal out of pullback
        m5_last = df_m5.iloc[-2]
        m5_close = float(m5_last["close"])
        m5_open = float(m5_last["open"])
        current_bid = symbol_info.get("bid", m5_close)
        current_ask = symbol_info.get("ask", m5_close)

        direction = h1_bias
        if direction == "BUY":
            # Rejection / Bullish close on M5
            is_trigger = m5_close > m5_open and m5_close > float(m5_last.get("ema_20", m5_close))
            if is_trigger:
                sl = min(float(m5_last["low"]), m15_ema50) - (m15_atr * 0.5)
                risk = current_ask - sl
                if risk > 0:
                    tp = current_ask + (risk * 2.0)  # 1:2 RR baseline
                    candidates.append({
                        "strategy": self.name,
                        "direction": "BUY",
                        "fingerprint": f"TF_BUY_{m15_last['timestamp_utc'].strftime('%Y%m%d%H%M')}",
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
                            "entry_price": round(m15_ema20, 2),
                            "stop_loss": sl,
                            "take_profit": tp,
                            "risk_reward": round((tp - m15_ema20) / (m15_ema20 - sl), 2) if (m15_ema20 - sl) > 0 else 0,
                            "invalidation_price": sl
                        },
                        "rationale": "H1 Bullish bias + M15 EMA pullback + M5 trigger bar reclaim EMA20."
                    })
        else:
            is_trigger = m5_close < m5_open and m5_close < float(m5_last.get("ema_20", m5_close))
            if is_trigger:
                sl = max(float(m5_last["high"]), m15_ema50) + (m15_atr * 0.5)
                risk = sl - current_bid
                if risk > 0:
                    tp = current_bid - (risk * 2.0)
                    candidates.append({
                        "strategy": self.name,
                        "direction": "SELL",
                        "fingerprint": f"TF_SELL_{m15_last['timestamp_utc'].strftime('%Y%m%d%H%M')}",
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
                            "entry_price": round(m15_ema20, 2),
                            "stop_loss": sl,
                            "take_profit": tp,
                            "risk_reward": round((m15_ema20 - tp) / (sl - m15_ema20), 2) if (sl - m15_ema20) > 0 else 0,
                            "invalidation_price": sl
                        },
                        "rationale": "H1 Bearish bias + M15 EMA pullback + M5 trigger bar reject EMA20."
                    })

        return candidates

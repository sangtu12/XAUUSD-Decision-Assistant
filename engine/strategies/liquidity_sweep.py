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

        # 1. Detect M15 Swings with institutional lookback=5
        swings = FeatureEngine.detect_swings(df_m15, lookback=5)
        swing_highs = swings["swing_highs"]
        swing_lows = swings["swing_lows"]

        if not swing_highs and not swing_lows:
            return candidates

        m15_last = df_m15.iloc[-2]
        m15_atr = float(m15_last.get("atr_14", 2.0))
        m15_ema20 = float(m15_last.get("ema_20", 0.0))

        m5_last = df_m5.iloc[-2]
        m5_prev1 = df_m5.iloc[-3]
        m5_prev2 = df_m5.iloc[-4]
        m5_high = float(m5_last["high"])
        m5_low = float(m5_last["low"])
        m5_close = float(m5_last["close"])
        m5_open = float(m5_last["open"])
        m5_atr = float(m5_last.get("atr_14", 1.5))
        current_bid = symbol_info.get("bid", m5_close)
        current_ask = symbol_info.get("ask", m5_close)
        trend_regime = regime.get("trend_regime", "TRANSITION")

        # 2. Bullish Liquidity Sweep (M15 Swing Low swept + M5 Market Structure Shift)
        if swing_lows:
            recent_low = swing_lows[-1]["price"]
            # Price swept below recent swing low in recent bars
            sweep_occurred = (m5_low < recent_low or float(m5_prev1["low"]) < recent_low)
            # Reclaimed above swing low
            reclaimed = m5_close > recent_low
            # MSS: M5 bar is bullish and broke above recent local M5 swing high
            local_m5_high = max(float(m5_prev1["high"]), float(m5_prev2["high"]))
            mss_confirmed = (m5_close > m5_open) and (m5_close > local_m5_high)

            if sweep_occurred and reclaimed and mss_confirmed:
                sl = min(m5_low, float(m5_prev1["low"])) - (m5_atr * 0.3)
                risk = current_ask - sl
                if risk > 0:
                    # In BEARISH trend: treat as counter-trend retest/rebound towards M15 EMA
                    if trend_regime == "BEARISH_TREND" and m15_ema20 > current_ask:
                        tp1 = min(current_ask + (risk * 2.0), m15_ema20)
                        tp2 = m15_ema20
                        tp3 = m15_ema20 + (risk * 1.5)
                        rationale = f"Bullish Sweep + M5 MSS: Retest bounce in Bearish Trend targeting M15 EMA20 ({round(m15_ema20, 2)})."
                    else:
                        tp1 = current_ask + (risk * 2.0)
                        tp2 = current_ask + (risk * 3.5)
                        tp3 = current_ask + (risk * 5.0)
                        rationale = f"Bullish Liquidity Sweep: M15 swing low {round(recent_low, 2)} swept with M5 MSS confirmation."

                    rr = round((tp1 - current_ask) / risk, 2)
                    if rr >= 1.5:
                        candidates.append({
                            "strategy": self.name,
                            "direction": "BUY",
                            "fingerprint": f"SWEEP_BUY_{round(recent_low, 1)}_{m5_last['timestamp_utc'].strftime('%Y%m%d%H%M')}",
                            "market_plan": {
                                "entry_type": "MARKET",
                                "reference_price": current_ask,
                                "entry_price": current_ask,
                                "stop_loss": sl,
                                "take_profit": tp1,
                                "take_profit_2": tp2,
                                "take_profit_3": tp3,
                                "risk_reward": rr,
                                "invalidation_price": sl
                            },
                            "limit_plan": {
                                "entry_type": "BUY_LIMIT",
                                "entry_price": round(recent_low, 2),
                                "stop_loss": sl,
                                "take_profit": tp1,
                                "take_profit_2": tp2,
                                "take_profit_3": tp3,
                                "risk_reward": round((tp1 - recent_low) / (recent_low - sl), 2) if (recent_low - sl) > 0 else 0,
                                "invalidation_price": sl
                            },
                            "rationale": rationale
                        })

        # 3. Bearish Liquidity Sweep (M15 Swing High swept + M5 Market Structure Shift)
        if swing_highs:
            recent_high = swing_highs[-1]["price"]
            sweep_occurred = (m5_high > recent_high or float(m5_prev1["high"]) > recent_high)
            rejected = m5_close < recent_high
            local_m5_low = min(float(m5_prev1["low"]), float(m5_prev2["low"]))
            mss_confirmed = (m5_close < m5_open) and (m5_close < local_m5_low)

            if sweep_occurred and rejected and mss_confirmed:
                sl = max(m5_high, float(m5_prev1["high"])) + (m5_atr * 0.3)
                risk = sl - current_bid
                if risk > 0:
                    # In BULLISH trend: treat as counter-trend retest towards M15 EMA
                    if trend_regime == "BULLISH_TREND" and m15_ema20 > 0 and m15_ema20 < current_bid:
                        tp1 = max(current_bid - (risk * 2.0), m15_ema20)
                        tp2 = m15_ema20
                        tp3 = m15_ema20 - (risk * 1.5)
                        rationale = f"Bearish Sweep + M5 MSS: Retest pullback in Bullish Trend targeting M15 EMA20 ({round(m15_ema20, 2)})."
                    else:
                        tp1 = current_bid - (risk * 2.0)
                        tp2 = current_bid - (risk * 3.5)
                        tp3 = current_bid - (risk * 5.0)
                        rationale = f"Bearish Liquidity Sweep: M15 swing high {round(recent_high, 2)} swept with M5 MSS confirmation."

                    rr = round((current_bid - tp1) / risk, 2)
                    if rr >= 1.5:
                        candidates.append({
                            "strategy": self.name,
                            "direction": "SELL",
                            "fingerprint": f"SWEEP_SELL_{round(recent_high, 1)}_{m5_last['timestamp_utc'].strftime('%Y%m%d%H%M')}",
                            "market_plan": {
                                "entry_type": "MARKET",
                                "reference_price": current_bid,
                                "entry_price": current_bid,
                                "stop_loss": sl,
                                "take_profit": tp1,
                                "take_profit_2": tp2,
                                "take_profit_3": tp3,
                                "risk_reward": rr,
                                "invalidation_price": sl
                            },
                            "limit_plan": {
                                "entry_type": "SELL_LIMIT",
                                "entry_price": round(recent_high, 2),
                                "stop_loss": sl,
                                "take_profit": tp1,
                                "take_profit_2": tp2,
                                "take_profit_3": tp3,
                                "risk_reward": round((recent_high - tp1) / (sl - recent_high), 2) if (sl - recent_high) > 0 else 0,
                                "invalidation_price": sl
                            },
                            "rationale": rationale
                        })

        return candidates

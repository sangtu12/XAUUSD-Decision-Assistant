import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import pandas as pd
import numpy as np

from engine.feature_engine import FeatureEngine
from engine.regime_detector import RegimeDetector
from engine.strategies.trend_following import TrendFollowingStrategy
from engine.strategies.liquidity_sweep import LiquiditySweepStrategy
from engine.strategies.breakout_retest import BreakoutRetestStrategy

logger = logging.getLogger(__name__)

class HistoricalBacktestEngine:
    def __init__(self):
        self.strategies = [
            TrendFollowingStrategy(),
            LiquiditySweepStrategy(),
            BreakoutRetestStrategy()
        ]

    def run_backtest(
        self,
        timeframe_dfs: Dict[str, pd.DataFrame],
        initial_balance_usd: float = 10000.0,
        risk_per_trade_pct: float = 1.0,
        enable_breakeven: bool = True,
        enable_trailing_runner: bool = True
    ) -> Dict[str, Any]:
        """Runs a fast multi-timeframe backtest over historical candles."""
        df_m5 = timeframe_dfs.get("M5")
        df_m15 = timeframe_dfs.get("M15")
        df_h1 = timeframe_dfs.get("H1")
        df_h4 = timeframe_dfs.get("H4")

        if df_m5 is None or len(df_m5) < 60:
            return {"error": "INSUFFICIENT_M5_DATA"}

        # Precompute features
        feat_dfs = {
            "M5": FeatureEngine.compute_all_features(df_m5),
            "M15": FeatureEngine.compute_all_features(df_m15) if df_m15 is not None else None,
            "H1": FeatureEngine.compute_all_features(df_h1) if df_h1 is not None else None,
            "H4": FeatureEngine.compute_all_features(df_h4) if df_h4 is not None else None,
        }

        trades: List[Dict[str, Any]] = []
        active_trade: Optional[Dict[str, Any]] = None
        peak_equity = initial_balance_usd
        current_equity = initial_balance_usd
        max_drawdown_pct = 0.0
        r_history: List[float] = []

        total_bars = len(df_m5)
        # Warmup 50 bars
        for i in range(50, total_bars):
            current_bar = df_m5.iloc[i]
            cur_time = current_bar["timestamp_utc"]
            cur_high = float(current_bar["high"])
            cur_low = float(current_bar["low"])
            cur_close = float(current_bar["close"])
            cur_spread = float(current_bar.get("spread", 0.35)) / 100.0

            # 1. Manage Active Trade if any
            if active_trade:
                side = active_trade["direction"]
                entry = active_trade["entry_price"]
                sl = active_trade["stop_loss"]
                tp1 = active_trade["take_profit_1"]
                tp2 = active_trade.get("take_profit_2", tp1)
                tp3 = active_trade.get("take_profit_3", tp1)
                risk = active_trade["risk_distance"]

                closed = False
                exit_price = None
                outcome = None
                r_achieved = 0.0
                validity = "VALID_SETUP"

                if side == "BUY":
                    float_r = (cur_high - entry) / risk
                    active_trade["max_r"] = max(active_trade.get("max_r", 0.0), float_r)

                    # Auto-breakeven at +1.2R
                    if enable_breakeven and float_r >= 1.2 and not active_trade.get("be_set"):
                        active_trade["stop_loss"] = entry + cur_spread
                        active_trade["be_set"] = True

                    # Trailing Stop for Runner
                    if enable_trailing_runner and float_r >= 3.0:
                        active_trade["stop_loss"] = max(active_trade["stop_loss"], entry + (risk * 1.5))
                    if enable_trailing_runner and float_r >= 4.5:
                        active_trade["stop_loss"] = max(active_trade["stop_loss"], entry + (risk * 3.0))

                    # Check TP3 (1:5+ Runner)
                    if cur_high >= tp3:
                        closed = True
                        exit_price = tp3
                        outcome = "TP_HIT"
                        r_achieved = round((tp3 - entry) / risk, 2)
                    # Check SL / Breakeven
                    elif cur_low <= active_trade["stop_loss"]:
                        closed = True
                        exit_price = active_trade["stop_loss"]
                        if active_trade.get("be_set"):
                            if active_trade.get("max_r", 0.0) >= 2.0:
                                outcome = "TP_HIT"
                                r_achieved = round((exit_price - entry) / risk, 2)
                            else:
                                outcome = "BREAKEVEN"
                                r_achieved = 0.0
                        else:
                            outcome = "SL_HIT"
                            r_achieved = -1.0
                            if active_trade.get("max_r", 0.0) < 0.3:
                                validity = "INVALID_SETUP"
                else:  # SELL
                    float_r = (entry - cur_low) / risk
                    active_trade["max_r"] = max(active_trade.get("max_r", 0.0), float_r)

                    if enable_breakeven and float_r >= 1.2 and not active_trade.get("be_set"):
                        active_trade["stop_loss"] = entry - cur_spread
                        active_trade["be_set"] = True

                    if enable_trailing_runner and float_r >= 3.0:
                        active_trade["stop_loss"] = min(active_trade["stop_loss"], entry - (risk * 1.5))
                    if enable_trailing_runner and float_r >= 4.5:
                        active_trade["stop_loss"] = min(active_trade["stop_loss"], entry - (risk * 3.0))

                    if cur_low <= tp3:
                        closed = True
                        exit_price = tp3
                        outcome = "TP_HIT"
                        r_achieved = round((entry - tp3) / risk, 2)
                    elif cur_high >= active_trade["stop_loss"]:
                        closed = True
                        exit_price = active_trade["stop_loss"]
                        if active_trade.get("be_set"):
                            if active_trade.get("max_r", 0.0) >= 2.0:
                                outcome = "TP_HIT"
                                r_achieved = round((entry - exit_price) / risk, 2)
                            else:
                                outcome = "BREAKEVEN"
                                r_achieved = 0.0
                        else:
                            outcome = "SL_HIT"
                            r_achieved = -1.0
                            if active_trade.get("max_r", 0.0) < 0.3:
                                validity = "INVALID_SETUP"

                if closed:
                    # Update equity
                    risk_amount = current_equity * (risk_per_trade_pct / 100.0)
                    pnl_usd = risk_amount * r_achieved
                    current_equity += pnl_usd
                    if current_equity > peak_equity:
                        peak_equity = current_equity
                    dd_pct = ((peak_equity - current_equity) / peak_equity) * 100.0
                    if dd_pct > max_drawdown_pct:
                        max_drawdown_pct = dd_pct

                    r_history.append(r_achieved)
                    trades.append({
                        "trade_num": len(trades) + 1,
                        "strategy": active_trade["strategy"],
                        "direction": active_trade["direction"],
                        "entry_time": str(active_trade["entry_time"]),
                        "exit_time": str(cur_time),
                        "entry_price": round(entry, 2),
                        "exit_price": round(exit_price, 2),
                        "outcome": outcome,
                        "validity": validity,
                        "r_achieved": r_achieved,
                        "pnl_usd": round(pnl_usd, 2),
                        "equity": round(current_equity, 2)
                    })
                    active_trade = None

            # 2. If no active trade, scan for new setups
            if not active_trade:
                # Slice historical context up to bar i
                sub_dfs = {}
                for tf_key, full_df in feat_dfs.items():
                    if full_df is not None:
                        sub_dfs[tf_key] = full_df[full_df["timestamp_utc"] <= cur_time]

                if "M15" in sub_dfs and len(sub_dfs["M15"]) >= 30:
                    regime = RegimeDetector.classify(sub_dfs["M15"])
                    sym_info = {"bid": cur_close, "ask": cur_close + cur_spread}

                    for strat in self.strategies:
                        setups = strat.evaluate(sub_dfs, regime, sym_info)
                        if setups:
                            s = setups[0]
                            plan = s.get("market_plan")
                            if plan and plan.get("entry_price"):
                                ent = plan["entry_price"]
                                sl = plan["stop_loss"]
                                risk_dist = abs(ent - sl)
                                if risk_dist > 0:
                                    active_trade = {
                                        "strategy": s["strategy"],
                                        "direction": s["direction"],
                                        "entry_time": cur_time,
                                        "entry_price": ent,
                                        "stop_loss": sl,
                                        "take_profit_1": plan["take_profit"],
                                        "take_profit_2": plan.get("take_profit_2", plan["take_profit"]),
                                        "take_profit_3": plan.get("take_profit_3", plan["take_profit"]),
                                        "risk_distance": risk_dist,
                                        "be_set": False,
                                        "max_r": 0.0
                                    }
                                    break

        # Calculate metrics
        total_trades = len(trades)
        wins = [t for t in trades if t["r_achieved"] > 0]
        losses = [t for t in trades if t["r_achieved"] < 0]
        bes = [t for t in trades if t["r_achieved"] == 0]
        valid_setups = [t for t in trades if t["validity"] == "VALID_SETUP"]

        win_rate = (len(wins) / total_trades * 100.0) if total_trades > 0 else 0.0
        gross_profit_r = sum(t["r_achieved"] for t in wins)
        gross_loss_r = abs(sum(t["r_achieved"] for t in losses))
        profit_factor = round(gross_profit_r / gross_loss_r, 2) if gross_loss_r > 0 else (gross_profit_r if gross_profit_r > 0 else 0.0)
        net_r = round(sum(r_history), 2)
        avg_r = round(net_r / total_trades, 2) if total_trades > 0 else 0.0

        return {
            "total_trades": total_trades,
            "win_rate_pct": round(win_rate, 2),
            "tp_hits": len(wins),
            "sl_hits": len(losses),
            "breakeven_count": len(bes),
            "valid_setups_pct": round(len(valid_setups) / total_trades * 100.0, 2) if total_trades > 0 else 0.0,
            "profit_factor": profit_factor,
            "net_r": net_r,
            "avg_r_per_trade": avg_r,
            "max_drawdown_pct": round(max_drawdown_pct, 2),
            "final_equity_usd": round(current_equity, 2),
            "return_pct": round(((current_equity - initial_balance_usd) / initial_balance_usd) * 100.0, 2),
            "recent_trades": trades[-20:]
        }

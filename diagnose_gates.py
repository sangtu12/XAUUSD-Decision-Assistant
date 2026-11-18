import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from collector.mt5_client import MT5Client
from config.settings import settings
from engine.feature_engine import FeatureEngine
from engine.regime_detector import RegimeDetector
from engine.strategies.trend_following import TrendFollowingStrategy
from engine.strategies.liquidity_sweep import LiquiditySweepStrategy
from engine.strategies.breakout_retest import BreakoutRetestStrategy
from engine.entry_planner import EntryPlanner
from engine.risk_engine import RiskEngine

def diagnose():
    mt5 = MT5Client(path=settings.MT5_PATH)
    if not mt5.connect():
        print("MT5 connect failed")
        return
    sym = mt5.find_gold_symbol(settings.MT5_SYMBOL)
    market_info = mt5.get_symbol_info(sym)
    print(f"--- DIAGNOSTIK KONDISI PASAR LIVE ({sym}) ---")
    print(f"Bid: {market_info['bid']} | Ask: {market_info['ask']} | Spread: {market_info['spread']} pts (USD {(market_info['ask']-market_info['bid']):.2f})")

    timeframe_dfs = {}
    for tf in ["M5", "M15", "H1", "H4"]:
        df = mt5.fetch_rates(sym, tf, count=100)
        df_feat = FeatureEngine.compute_all_features(df)
        timeframe_dfs[tf] = df_feat

    regime = RegimeDetector.classify(timeframe_dfs["M15"])
    print(f"\nRegime: {regime['trend_regime']} | Volatilitas: {regime['volatility_regime']}")

    print("\n1. STRATEGI: TrendFollowing")
    tf_strat = TrendFollowingStrategy()
    df_h1 = timeframe_dfs["H1"]
    df_m15 = timeframe_dfs["M15"]
    df_m5 = timeframe_dfs["M5"]
    h1_last = df_h1.iloc[-2]
    h1_bias = "BUY" if h1_last["close"] > h1_last.get("ema_50", h1_last["close"]) else "SELL"
    print(f" - H1 Bias: {h1_bias} (Close: {h1_last['close']}, EMA50: {h1_last['ema_50']:.2f})")
    m15_last = df_m15.iloc[-2]
    m15_close = m15_last["close"]
    m15_ema20 = m15_last["ema_20"]
    m15_ema50 = m15_last["ema_50"]
    m15_atr = m15_last["atr_14"]
    print(f" - M15 Status: Close={m15_close:.2f}, EMA20={m15_ema20:.2f}, EMA50={m15_ema50:.2f}, ATR={m15_atr:.2f}")
    
    in_pb = False
    if h1_bias == "BUY" and (m15_close <= m15_ema20 or abs(m15_close - m15_ema20) < m15_atr * 0.5):
        in_pb = True
    elif h1_bias == "SELL" and (m15_close >= m15_ema20 or abs(m15_close - m15_ema20) < m15_atr * 0.5):
        in_pb = True
    print(f" - M15 Pullback Zone: {in_pb}")

    m5_last = df_m5.iloc[-2]
    m5_close = m5_last["close"]
    m5_open = m5_last["open"]
    m5_ema20 = m5_last["ema_20"]
    print(f" - M5 Trigger Bar: Open={m5_open:.2f}, Close={m5_close:.2f}, EMA20={m5_ema20:.2f}")

    setups_tf = tf_strat.evaluate(timeframe_dfs, regime, market_info)
    print(f" - TrendFollowing Setup Candidates: {len(setups_tf)}")

    print("\n2. STRATEGI: LiquiditySweepReversal")
    ls_strat = LiquiditySweepStrategy()
    setups_ls = ls_strat.evaluate(timeframe_dfs, regime, market_info)
    swings = FeatureEngine.detect_swings(df_m15, lookback=3)
    print(f" - M15 Swings: Highs count={len(swings['swing_highs'])}, Lows count={len(swings['swing_lows'])}")
    if swings['swing_highs']:
        print(f"   Recent Swing High: {swings['swing_highs'][-1]['price']}")
    if swings['swing_lows']:
        print(f"   Recent Swing Low: {swings['swing_lows'][-1]['price']}")
    print(f" - LiquiditySweep Setup Candidates: {len(setups_ls)}")

    print("\n3. STRATEGI: BreakoutRetest")
    br_strat = BreakoutRetestStrategy()
    setups_br = br_strat.evaluate(timeframe_dfs, regime, market_info)
    print(f" - BreakoutRetest Setup Candidates: {len(setups_br)}")

    all_setups = setups_tf + setups_ls + setups_br
    print(f"\nTotal Kandidat Setup Terdeteksi: {len(all_setups)}")

    for s in all_setups:
        print(f"\nMengecek Setup: {s['strategy']} {s['direction']}")
        plan = EntryPlanner.choose_entry(s, market_info)
        print(f" - Entry Plan terpilih: {plan['selected_type'] if plan else 'None'}")
        if plan:
            is_valid, reason = RiskEngine.validate_plan(plan, market_info, regime)
            print(f" - Risk Engine Valid: {is_valid} (Reason: {reason})")

    mt5.disconnect()

if __name__ == "__main__":
    diagnose()

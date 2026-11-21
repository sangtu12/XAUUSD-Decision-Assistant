import unittest
import sys
import os
from datetime import datetime, timedelta
from decimal import Decimal
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.feature_engine import FeatureEngine
from engine.regime_detector import RegimeDetector
from engine.strategies.trend_following import TrendFollowingStrategy
from engine.strategies.liquidity_sweep import LiquiditySweepStrategy
from engine.strategies.breakout_retest import BreakoutRetestStrategy
from engine.entry_planner import EntryPlanner
from engine.risk_engine import RiskEngine
from collector.data_quality import DataQualityService
from database.connection import SessionLocal
from services.signal_publisher import SignalPublisher
from services.signal_tracker import SignalTracker
from database.models import Signal, StrategySetup

class TestCoreEngine(unittest.TestCase):
    def setUp(self):
        # Generate 100 synthetic candles
        times = [datetime(2026, 1, 1) + timedelta(minutes=5 * i) for i in range(100)]
        prices = [3500.0 + i * 0.5 for i in range(100)]
        self.df_bullish = pd.DataFrame({
            "timestamp_utc": times,
            "open": [p - 0.2 for p in prices],
            "high": [p + 0.8 for p in prices],
            "low": [p - 0.5 for p in prices],
            "close": prices,
            "tick_volume": [1000] * 100,
            "spread": [40] * 100
        })

    def test_feature_engine(self):
        df_feat = FeatureEngine.compute_all_features(self.df_bullish)
        self.assertIn("ema_20", df_feat.columns)
        self.assertIn("ema_50", df_feat.columns)
        self.assertIn("rsi_14", df_feat.columns)
        self.assertIn("atr_14", df_feat.columns)

    def test_swings_detection(self):
        swings = FeatureEngine.detect_swings(self.df_bullish, lookback=3)
        self.assertIn("swing_highs", swings)
        self.assertIn("swing_lows", swings)

    def test_regime_detector(self):
        df_feat = FeatureEngine.compute_all_features(self.df_bullish)
        regime = RegimeDetector.classify(df_feat)
        self.assertIn("trend_regime", regime)
        self.assertIn("volatility_regime", regime)

    def test_data_quality(self):
        dq = DataQualityService(max_spread_cents=50.0)
        valid, _ = dq.validate_tick({"bid": 3500.0, "ask": 3500.30})
        self.assertTrue(valid)

        invalid_spread, _ = dq.validate_tick({"bid": 3500.0, "ask": 3501.00})
        self.assertFalse(invalid_spread)

    def test_risk_engine(self):
        market = {"bid": 3500.0, "ask": 3500.30}
        regime = {"volatility_regime": "NORMAL"}
        
        # Valid plan
        valid_plan = {
            "entry_price": 3500.30,
            "stop_loss": 3498.30, # risk = 2.0
            "take_profit": 3504.30, # reward = 4.0 (RR 2.0)
        }
        ok, reason = RiskEngine.validate_plan(valid_plan, market, regime)
        self.assertTrue(ok, f"Expected valid plan, got {reason}")

        # Invalid RR (< 1.5)
        bad_rr_plan = {
            "entry_price": 3500.30,
            "stop_loss": 3498.30, # risk = 2.0
            "take_profit": 3501.30, # reward = 1.0 (RR 0.5)
        }
        ok, reason = RiskEngine.validate_plan(bad_rr_plan, market, regime)
        self.assertFalse(ok)
        self.assertIn("RISK_REWARD_BELOW_MINIMUM", reason)

    def test_entry_planner(self):
        market = {"bid": 3500.0, "ask": 3500.30}
        setup = {
            "direction": "BUY",
            "market_plan": {
                "reference_price": 3500.30,
                "stop_loss": 3495.0,
                "take_profit": 3510.0
            },
            "limit_plan": {
                "entry_price": 3498.0,
                "stop_loss": 3495.0,
                "take_profit": 3510.0
            }
        }
        plan = EntryPlanner.choose_entry(setup, market, max_chase_points=30.0)
        self.assertIsNotNone(plan)
        self.assertEqual(plan["selected_type"], "MARKET")

if __name__ == "__main__":
    unittest.main()

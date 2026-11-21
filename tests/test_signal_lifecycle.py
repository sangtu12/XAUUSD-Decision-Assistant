import unittest
import sys
import os
import asyncio
from datetime import datetime
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import SessionLocal
from database.models import Signal, StrategySetup, SignalEvent, SignalEvaluation
from services.signal_publisher import SignalPublisher
from services.signal_tracker import SignalTracker

from unittest.mock import AsyncMock

class TestSignalLifecycle(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.db = SessionLocal()
        self.publisher = SignalPublisher(self.db)
        self.publisher.notifier.send_message = AsyncMock(return_value=True)
        self.tracker = SignalTracker(self.db)

    def tearDown(self):
        self.db.close()

    async def test_limit_fill_and_tp(self):
        setup_data = {
            "strategy": "LiquiditySweep",
            "direction": "BUY",
            "fingerprint": f"TEST_LIFECYCLE_BUY_{datetime.utcnow().timestamp()}",
            "rationale": "Test limit fill and take profit"
        }
        entry_plan = {
            "selected_type": "BUY_LIMIT",
            "entry_price": 3500.0,
            "stop_loss": 3490.0,
            "take_profit": 3520.0,
            "risk_reward": 2.0,
            "reference_price": 3505.0
        }
        market_data = {"bid": 3504.80, "ask": 3505.00, "spread": 20}

        sig = await self.publisher.publish_signal(
            setup_data=setup_data,
            entry_plan=entry_plan,
            features_snapshot={},
            regime_snapshot={"trend_regime": "BULLISH", "volatility_regime": "NORMAL"},
            market_data=market_data
        )
        self.assertIsNotNone(sig)
        self.assertEqual(sig.status, "WAITING_FOR_ENTRY")

        # 1. Price drops and touches entry (ask <= 3500.0) -> FILLED
        events = self.tracker.update_all_signals({"bid": 3499.80, "ask": 3500.00})
        self.db.refresh(sig)
        self.assertEqual(sig.status, "MONITORING")

        # 2. Price rises and hits TP (bid >= 3520.0) -> TP_HIT
        events = self.tracker.update_all_signals({"bid": 3520.50, "ask": 3520.80})
        self.db.refresh(sig)
        self.assertEqual(sig.status, "TP_HIT")

        # Check evaluation recorded
        eval_record = self.db.query(SignalEvaluation).filter(SignalEvaluation.signal_id == sig.signal_id).first()
        self.assertIsNotNone(eval_record)
        self.assertEqual(eval_record.trade_outcome, "TP_HIT")
        self.assertEqual(float(eval_record.r_multiple), 2.0)

    async def test_limit_target_reached_before_entry_expired(self):
        setup_data = {
            "strategy": "BreakoutRetest",
            "direction": "BUY",
            "fingerprint": f"TEST_EXPIRED_TP_{datetime.utcnow().timestamp()}",
            "rationale": "Test expired when TP hit before fill"
        }
        entry_plan = {
            "selected_type": "BUY_LIMIT",
            "entry_price": 3500.0,
            "stop_loss": 3490.0,
            "take_profit": 3520.0,
            "risk_reward": 2.0,
            "reference_price": 3505.0
        }
        market_data = {"bid": 3504.80, "ask": 3505.00, "spread": 20}

        sig = await self.publisher.publish_signal(
            setup_data=setup_data,
            entry_plan=entry_plan,
            features_snapshot={},
            regime_snapshot={"trend_regime": "BULLISH", "volatility_regime": "NORMAL"},
            market_data=market_data
        )
        self.assertEqual(sig.status, "WAITING_FOR_ENTRY")

        # Price rockets to TP directly without dropping to entry
        events = self.tracker.update_all_signals({"bid": 3521.00, "ask": 3521.30})
        self.db.refresh(sig)
        self.assertEqual(sig.status, "EXPIRED")

        eval_record = self.db.query(SignalEvaluation).filter(SignalEvaluation.signal_id == sig.signal_id).first()
        self.assertIsNotNone(eval_record)
        self.assertEqual(eval_record.trade_outcome, "EXPIRED")

    async def test_auto_breakeven_protection(self):
        setup_data = {
            "strategy": "TrendFollowing",
            "direction": "BUY",
            "fingerprint": f"TEST_BE_{datetime.utcnow().timestamp()}",
            "rationale": "Test auto breakeven activation"
        }
        entry_plan = {
            "selected_type": "MARKET",
            "entry_price": 3500.0,
            "stop_loss": 3490.0, # risk = 10.0
            "take_profit": 3520.0,
            "take_profit_3": 3550.0, # 1:5+ runner
            "risk_reward": 2.0,
            "reference_price": 3500.0
        }
        market_data = {"bid": 3500.00, "ask": 3500.30, "spread": 30}

        sig = await self.publisher.publish_signal(
            setup_data=setup_data,
            entry_plan=entry_plan,
            features_snapshot={},
            regime_snapshot={"trend_regime": "BULLISH", "volatility_regime": "NORMAL"},
            market_data=market_data
        )
        self.assertEqual(sig.status, "PUBLISHED")

        # Initial tracker cycle transitions MARKET order to MONITORING and simulates fill
        self.tracker.update_all_signals({"bid": 3500.00, "ask": 3500.30})
        self.db.refresh(sig)
        self.assertEqual(sig.status, "MONITORING")

        # Price rises to +1.3R (3513.0) -> Triggers Breakeven
        self.tracker.update_all_signals({"bid": 3513.00, "ask": 3513.30})
        self.db.refresh(sig)
        self.assertTrue(sig.is_breakeven_set)
        self.assertGreaterEqual(sig.stop_loss, Decimal("3500.0"))

        # Price reverses back to Breakeven level -> Protected exit
        self.tracker.update_all_signals({"bid": 3499.50, "ask": 3499.80})
        self.db.refresh(sig)
        self.assertEqual(sig.status, "BREAKEVEN")

        eval_record = self.db.query(SignalEvaluation).filter(SignalEvaluation.signal_id == sig.signal_id).first()
        self.assertIsNotNone(eval_record)
        self.assertEqual(eval_record.trade_outcome, "BREAKEVEN")
        self.assertEqual(eval_record.setup_validity, "VALID_SETUP")

    async def test_invalid_setup_immediate_sl(self):
        setup_data = {
            "strategy": "LiquiditySweep",
            "direction": "BUY",
            "fingerprint": f"TEST_INVALID_{datetime.utcnow().timestamp()}",
            "rationale": "Test immediate SL invalid setup"
        }
        entry_plan = {
            "selected_type": "MARKET",
            "entry_price": 3500.0,
            "stop_loss": 3490.0,
            "take_profit": 3520.0,
            "risk_reward": 2.0
        }
        market_data = {"bid": 3500.00, "ask": 3500.30, "spread": 30}

        sig = await self.publisher.publish_signal(
            setup_data=setup_data,
            entry_plan=entry_plan,
            features_snapshot={},
            regime_snapshot={"trend_regime": "BULLISH", "volatility_regime": "NORMAL"},
            market_data=market_data
        )
        self.assertEqual(sig.status, "PUBLISHED")
        # First cycle transitions MARKET order to MONITORING
        self.tracker.update_all_signals({"bid": 3500.00, "ask": 3500.30})

        # Price immediately crashes to SL without moving in profit
        self.tracker.update_all_signals({"bid": 3489.00, "ask": 3489.30})
        self.db.refresh(sig)
        self.assertEqual(sig.status, "SL_HIT")

        eval_record = self.db.query(SignalEvaluation).filter(SignalEvaluation.signal_id == sig.signal_id).first()
        self.assertIsNotNone(eval_record)
        self.assertEqual(eval_record.setup_validity, "INVALID_SETUP")
        self.assertEqual(float(eval_record.r_multiple), -1.0)

if __name__ == "__main__":
    unittest.main()

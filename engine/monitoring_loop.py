import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, List

from config.settings import settings
from database.connection import SessionLocal
from collector.mt5_client import MT5Client
from collector.data_quality import DataQualityService
from collector.candle_builder import CandleNormalizer
from engine.feature_engine import FeatureEngine
from engine.regime_detector import RegimeDetector
from engine.strategies.trend_following import TrendFollowingStrategy
from engine.strategies.liquidity_sweep import LiquiditySweepStrategy
from engine.strategies.breakout_retest import BreakoutRetestStrategy
from engine.entry_planner import EntryPlanner
from engine.risk_engine import RiskEngine
from services.signal_publisher import SignalPublisher
from services.signal_tracker import SignalTracker

logger = logging.getLogger(__name__)

class MonitoringEngine:
    def __init__(self):
        self.mt5 = MT5Client(
            path=settings.MT5_PATH,
            login=settings.MT5_LOGIN,
            password=settings.MT5_PASSWORD,
            server=settings.MT5_SERVER
        )
        self.data_quality = DataQualityService(
            max_spread_cents=float(settings.MAX_SPREAD_CENTS)
        )
        self.strategies = [
            TrendFollowingStrategy(),
            LiquiditySweepStrategy(),
            BreakoutRetestStrategy()
        ]
        self.is_running = False
        self.latest_state: Dict[str, Any] = {}

    async def run_single_iteration(self) -> Dict[str, Any]:
        """Runs one full cycle of Section 14.1 Monitoring Loop."""
        db = SessionLocal()
        try:
            # 1. MT5 connection check
            if not self.mt5.initialized:
                if not self.mt5.connect():
                    return {"status": "ERROR", "reason": "MT5_CONNECT_FAILED"}

            gold_symbol = self.mt5.find_gold_symbol(settings.MT5_SYMBOL)
            if not gold_symbol:
                return {"status": "ERROR", "reason": "GOLD_SYMBOL_NOT_FOUND"}

            # 2. Fetch live tick / market info
            market_info = self.mt5.get_symbol_info(gold_symbol)
            is_valid_tick, tick_err = self.data_quality.validate_tick(market_info)
            if not is_valid_tick:
                logger.warning(f"Tick invalid: {tick_err}")
                return {
                    "status": "WAIT_INVALID_DATA",
                    "reason": tick_err,
                    "symbol": gold_symbol,
                    "price": market_info.get("bid") if market_info else None,
                    "bid": market_info.get("bid") if market_info else None,
                    "ask": market_info.get("ask") if market_info else None,
                    "spread": market_info.get("spread") if market_info else None,
                    "spread_usd": round(market_info.get("ask", 0) - market_info.get("bid", 0), 2) if market_info else None,
                    "regime": "WAIT_RISK_GATE",
                    "volatility": "EVALUATING",
                    "published_signals": [],
                    "tracked_events": []
                }

            # 3. Fetch rates across M5, M15, H1, H4
            timeframe_dfs = {}
            for tf in settings.timeframes_list:
                df = self.mt5.fetch_rates(gold_symbol, tf, count=100)
                is_valid_candles, candle_err = self.data_quality.validate_candles(df, tf)
                if not is_valid_candles:
                    logger.warning(f"Candles invalid on {tf}: {candle_err}")
                    continue
                # Persist to database
                CandleNormalizer.process_and_persist(db, gold_symbol, tf, df)
                # Compute features
                df_with_features = FeatureEngine.compute_all_features(df)
                timeframe_dfs[tf] = df_with_features

            if "M5" not in timeframe_dfs or "M15" not in timeframe_dfs:
                return {"status": "WAIT_INSUFFICIENT_TIMEFRAMES"}

            # 4. Regime Detection
            regime = RegimeDetector.classify(timeframe_dfs["M15"])

            # 5. Track existing active signals first
            tracker = SignalTracker(db)
            tracked_events = tracker.update_all_signals(market_info)

            # 6. Evaluate Strategies
            publisher = SignalPublisher(db)
            published_signals = []

            for strat in self.strategies:
                setups = strat.evaluate(timeframe_dfs, regime, market_info)
                for setup in setups:
                    # Choose entry type (Market vs Direct Limit)
                    entry_plan = EntryPlanner.choose_entry(setup, market_info)
                    if not entry_plan:
                        continue

                    # Risk Engine validation gate
                    is_risk_valid, risk_reason = RiskEngine.validate_plan(entry_plan, market_info, regime)
                    if not is_risk_valid:
                        logger.info(f"Setup rejected by Risk Engine: {risk_reason}")
                        continue

                    # Publish signal & store immutable snapshot
                    sig = await publisher.publish_signal(
                        setup_data=setup,
                        entry_plan=entry_plan,
                        features_snapshot=regime.get("evidence", {}),
                        regime_snapshot=regime,
                        market_data=market_info
                    )
                    if sig:
                        published_signals.append(str(sig.signal_id))

            res = {
                "status": "SUCCESS",
                "symbol": gold_symbol,
                "price": market_info.get("bid"),
                "bid": market_info.get("bid"),
                "ask": market_info.get("ask"),
                "spread": market_info.get("spread"),
                "spread_usd": round(market_info.get("ask", 0) - market_info.get("bid", 0), 2),
                "regime": regime.get("trend_regime"),
                "volatility": regime.get("volatility_regime"),
                "published_signals": published_signals,
                "tracked_events": tracked_events
            }
            self.latest_state = res
            return res
        finally:
            db.close()

    async def start(self, poll_interval_sec: int = 5):
        """Continuously loop and monitor market."""
        self.is_running = True
        logger.info("Starting XAUUSD Autonomous Monitoring Engine...")
        while self.is_running:
            try:
                res = await self.run_single_iteration()
                logger.info(f"Monitoring cycle: {res.get('status')} | Price: {res.get('price')} | Regime: {res.get('regime')}")
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}", exc_info=True)
            await asyncio.sleep(poll_interval_sec)

    def stop(self):
        self.is_running = False
        self.mt5.disconnect()
        logger.info("Monitoring engine stopped.")

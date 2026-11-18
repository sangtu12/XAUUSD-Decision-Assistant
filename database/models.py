import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import (
    Column, String, Integer, Numeric, Boolean, DateTime,
    ForeignKey, Text, Index
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class Instrument(Base):
    __tablename__ = "instruments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    broker = Column(String(64), nullable=False)
    symbol_broker = Column(String(32), nullable=False)   # e.g. "XAUUSD" or "GOLD"
    canonical_symbol = Column(String(32), default="XAUUSD", nullable=False)
    digits = Column(Integer, default=2, nullable=False)
    tick_size = Column(Numeric(12, 5), default=Decimal("0.01"), nullable=False)
    contract_size = Column(Numeric(12, 2), default=Decimal("100.0"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("idx_inst_broker_symbol", "broker", "symbol_broker", unique=True),
    )


class MarketBar(Base):
    __tablename__ = "market_bars"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(32), nullable=False)
    timeframe = Column(String(8), nullable=False)  # M5, M15, H1, H4
    timestamp_utc = Column(DateTime, nullable=False)
    open = Column(Numeric(12, 4), nullable=False)
    high = Column(Numeric(12, 4), nullable=False)
    low = Column(Numeric(12, 4), nullable=False)
    close = Column(Numeric(12, 4), nullable=False)
    tick_volume = Column(Integer, default=0, nullable=False)
    spread = Column(Numeric(10, 2), default=Decimal("0.0"), nullable=False)
    is_complete = Column(Boolean, default=True, nullable=False)  # False for bar index 0

    __table_args__ = (
        Index("idx_bar_sym_tf_time", "symbol", "timeframe", "timestamp_utc", unique=True),
    )


class MarketFeature(Base):
    __tablename__ = "market_features"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(32), nullable=False)
    timeframe = Column(String(8), nullable=False)
    timestamp_utc = Column(DateTime, nullable=False)
    features = Column(JSONB, nullable=False)  # indicators, swings, FVG, OB, etc.
    algorithm_version = Column(String(16), default="0.3", nullable=False)

    __table_args__ = (
        Index("idx_feat_sym_tf_time", "symbol", "timeframe", "timestamp_utc"),
    )


class MarketRegime(Base):
    __tablename__ = "market_regimes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(32), nullable=False)
    timestamp_utc = Column(DateTime, nullable=False)
    trend_regime = Column(String(32), nullable=False)  # BULLISH, BEARISH, RANGING, TRANSITION
    volatility_regime = Column(String(32), nullable=False)  # LOW, NORMAL, HIGH, EXTREME
    evidence = Column(JSONB, nullable=True)

    __table_args__ = (
        Index("idx_regime_sym_time", "symbol", "timestamp_utc"),
    )


class StrategySetup(Base):
    __tablename__ = "strategy_setups"

    setup_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    strategy_name = Column(String(64), nullable=False)  # TrendFollowing, LiquiditySweep, BreakoutRetest
    direction = Column(String(8), nullable=False)       # BUY, SELL
    fingerprint = Column(String(128), nullable=False)   # Dedup key
    status = Column(String(32), default="CANDIDATE", nullable=False)  # CANDIDATE, VALIDATED, INVALIDATED, EXPIRED
    rule_version = Column(String(16), default="0.3", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    signals = relationship("Signal", back_populates="setup")

    __table_args__ = (
        Index("idx_setup_fingerprint_status", "fingerprint", "status"),
    )


class Signal(Base):
    __tablename__ = "signals"

    signal_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    setup_id = Column(UUID(as_uuid=True), ForeignKey("strategy_setups.setup_id"), nullable=False)
    entry_type = Column(String(16), nullable=False)  # MARKET, BUY_LIMIT, SELL_LIMIT
    side = Column(String(8), nullable=False)        # BUY, SELL
    reference_price = Column(Numeric(12, 4), nullable=False)
    entry_price = Column(Numeric(12, 4), nullable=False)
    stop_loss = Column(Numeric(12, 4), nullable=False)
    take_profit = Column(Numeric(12, 4), nullable=False)
    risk_reward = Column(Numeric(8, 2), nullable=False)
    
    # Status lifecycle: PUBLISHED, WAITING_FOR_ENTRY, MONITORING, FILLED, EXPIRED, INVALIDATED, TP_HIT, SL_HIT, BREAKEVEN, AMBIGUOUS
    status = Column(String(32), default="PUBLISHED", nullable=False)
    published_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)
    
    setup = relationship("StrategySetup", back_populates="signals")
    snapshot = relationship("SignalSnapshot", uselist=False, back_populates="signal")
    events = relationship("SignalEvent", back_populates="signal")
    revisions = relationship("SignalRevision", back_populates="signal")
    evaluation = relationship("SignalEvaluation", uselist=False, back_populates="signal")

    __table_args__ = (
        Index("idx_signal_status", "status"),
        Index("idx_signal_published_at", "published_at"),
    )


class SignalSnapshot(Base):
    __tablename__ = "signal_snapshots"

    snapshot_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    signal_id = Column(UUID(as_uuid=True), ForeignKey("signals.signal_id"), nullable=False, unique=True)
    snapshot_data = Column(JSONB, nullable=False)  # Immutable record of market, indicators, PA, SMC, rationale
    captured_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    signal = relationship("Signal", back_populates="snapshot")


class SignalRevision(Base):
    __tablename__ = "signal_revisions"

    revision_id = Column(Integer, primary_key=True, autoincrement=True)
    signal_id = Column(UUID(as_uuid=True), ForeignKey("signals.signal_id"), nullable=False)
    timestamp_utc = Column(DateTime, default=datetime.utcnow, nullable=False)
    old_entry = Column(Numeric(12, 4), nullable=True)
    new_entry = Column(Numeric(12, 4), nullable=True)
    old_sl = Column(Numeric(12, 4), nullable=True)
    new_sl = Column(Numeric(12, 4), nullable=True)
    old_tp = Column(Numeric(12, 4), nullable=True)
    new_tp = Column(Numeric(12, 4), nullable=True)
    reason = Column(Text, nullable=False)

    signal = relationship("Signal", back_populates="revisions")


class SignalEvent(Base):
    __tablename__ = "signal_events"

    event_id = Column(Integer, primary_key=True, autoincrement=True)
    signal_id = Column(UUID(as_uuid=True), ForeignKey("signals.signal_id"), nullable=False)
    event_type = Column(String(32), nullable=False)  # PUBLISHED, TOUCHED, FILLED, INVALIDATED, EXPIRED, TP_HIT, SL_HIT, BE
    timestamp_utc = Column(DateTime, default=datetime.utcnow, nullable=False)
    price_at_event = Column(Numeric(12, 4), nullable=True)
    payload = Column(JSONB, nullable=True)

    signal = relationship("Signal", back_populates="events")

    __table_args__ = (
        Index("idx_event_sig_time", "signal_id", "timestamp_utc"),
    )


class SignalEvaluation(Base):
    __tablename__ = "signal_evaluations"

    evaluation_id = Column(Integer, primary_key=True, autoincrement=True)
    signal_id = Column(UUID(as_uuid=True), ForeignKey("signals.signal_id"), nullable=False, unique=True)
    
    # 3-Dimension evaluation as requested in Blueprint Section 13
    setup_validity = Column(String(32), nullable=False)  # VALID_SETUP, INVALID_SETUP, INCOMPLETE_SETUP
    trade_outcome = Column(String(32), nullable=False)   # TP_HIT, SL_HIT, BREAKEVEN, EXPIRED, CANCELLED, AMBIGUOUS
    analysis_quality = Column(JSONB, nullable=True)      # {"trend": true, "structure": true, "timing": false, ...}
    error_categories = Column(JSONB, nullable=True)      # ["TrendMisclassification", ...]
    r_multiple = Column(Numeric(8, 2), nullable=True)
    notes = Column(Text, nullable=True)
    evaluated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    signal = relationship("Signal", back_populates="evaluation")


class StrategyConfig(Base):
    __tablename__ = "strategy_configs"

    config_id = Column(Integer, primary_key=True, autoincrement=True)
    strategy_name = Column(String(64), nullable=False)
    parameters = Column(JSONB, nullable=False)
    version = Column(String(16), default="0.3", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class FundamentalEvent(Base):
    __tablename__ = "fundamental_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(128), nullable=False)
    currency = Column(String(8), default="USD", nullable=False)
    impact = Column(String(16), nullable=False)  # HIGH, MEDIUM, LOW
    timestamp_utc = Column(DateTime, nullable=False)
    actual = Column(String(32), nullable=True)
    forecast = Column(String(32), nullable=True)
    previous = Column(String(32), nullable=True)
    source = Column(String(64), default="BLS/FED", nullable=False)


class NotificationLog(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    signal_id = Column(UUID(as_uuid=True), nullable=True)
    channel = Column(String(32), default="TELEGRAM", nullable=False)
    delivery_status = Column(String(16), default="PENDING", nullable=False)  # PENDING, SENT, FAILED
    payload = Column(JSONB, nullable=False)
    error_message = Column(Text, nullable=True)
    sent_at = Column(DateTime, nullable=True)

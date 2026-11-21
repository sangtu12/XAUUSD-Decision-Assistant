import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from database.models import (
    StrategySetup, Signal, SignalSnapshot, SignalEvent, NotificationLog
)
from services.telegram_notifier import TelegramNotifier

logger = logging.getLogger(__name__)

class SignalPublisher:
    def __init__(self, db: Session):
        self.db = db
        self.notifier = TelegramNotifier()

    def is_duplicate(self, fingerprint: str) -> bool:
        """Check if an active setup with this fingerprint already exists."""
        existing = self.db.query(StrategySetup).filter(
            StrategySetup.fingerprint == fingerprint,
            StrategySetup.status.in_(["CANDIDATE", "VALIDATED"])
        ).first()
        return existing is not None

    async def publish_signal(
        self,
        setup_data: Dict[str, Any],
        entry_plan: Dict[str, Any],
        features_snapshot: Dict[str, Any],
        regime_snapshot: Dict[str, Any],
        market_data: Dict[str, Any]
    ) -> Optional[Signal]:
        fingerprint = setup_data.get("fingerprint", str(uuid.uuid4()))
        if self.is_duplicate(fingerprint):
            logger.info(f"Duplicate setup skipped: {fingerprint}")
            return None

        # 1. Create StrategySetup
        setup = StrategySetup(
            setup_id=uuid.uuid4(),
            strategy_name=setup_data.get("strategy", "Unknown"),
            direction=setup_data.get("direction", "BUY"),
            fingerprint=fingerprint,
            status="VALIDATED",
            rule_version="0.3",
            created_at=datetime.utcnow()
        )
        self.db.add(setup)
        self.db.flush()

        # 2. Create Signal
        entry_type = entry_plan.get("selected_type", "MARKET")
        side = setup_data.get("direction", "BUY")
        entry_price = Decimal(str(entry_plan.get("entry_price", 0.0)))
        stop_loss = Decimal(str(entry_plan.get("stop_loss", 0.0)))
        take_profit = Decimal(str(entry_plan.get("take_profit", 0.0)))
        tp2_val = entry_plan.get("take_profit_2")
        take_profit_2 = Decimal(str(tp2_val)) if tp2_val is not None else None
        tp3_val = entry_plan.get("take_profit_3")
        take_profit_3 = Decimal(str(tp3_val)) if tp3_val is not None else None
        risk_reward = Decimal(str(entry_plan.get("risk_reward", 2.0)))
        ref_price = Decimal(str(entry_plan.get("reference_price", entry_price)))

        signal = Signal(
            signal_id=uuid.uuid4(),
            setup_id=setup.setup_id,
            entry_type=entry_type,
            side=side,
            reference_price=ref_price,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            take_profit_2=take_profit_2,
            take_profit_3=take_profit_3,
            risk_reward=risk_reward,
            status="PUBLISHED" if entry_type == "MARKET" else "WAITING_FOR_ENTRY",
            published_at=datetime.utcnow()
        )
        self.db.add(signal)
        self.db.flush()

        # 3. Create Immutable Snapshot
        snapshot_payload = {
            "setup": setup_data,
            "entry_plan": {k: float(v) if isinstance(v, (Decimal, float)) else v for k, v in entry_plan.items()},
            "regime": regime_snapshot,
            "market": {k: float(v) if isinstance(v, (Decimal, float)) else v for k, v in market_data.items()},
            "features_summary": features_snapshot,
            "published_at_utc": datetime.utcnow().isoformat()
        }
        snapshot = SignalSnapshot(
            snapshot_id=uuid.uuid4(),
            signal_id=signal.signal_id,
            snapshot_data=snapshot_payload,
            captured_at=datetime.utcnow()
        )
        self.db.add(snapshot)

        # 4. Create SignalEvent
        event = SignalEvent(
            signal_id=signal.signal_id,
            event_type="PUBLISHED",
            timestamp_utc=datetime.utcnow(),
            price_at_event=entry_price,
            payload={"entry_type": entry_type, "side": side}
        )
        self.db.add(event)

        # 5. Telegram Notification
        msg_payload = {
            "strategy_name": setup.strategy_name,
            "entry_type": entry_type,
            "side": side,
            "entry_price": str(entry_price),
            "stop_loss": str(stop_loss),
            "take_profit": str(take_profit),
            "take_profit_2": str(take_profit_2) if take_profit_2 else "",
            "take_profit_3": str(take_profit_3) if take_profit_3 else "",
            "risk_reward": str(risk_reward),
            "spread": f"{round(market_data.get('ask', 0) - market_data.get('bid', 0), 2)}",
            "rationale": setup_data.get("rationale", "")
        }
        formatted_msg = self.notifier.format_signal_message(msg_payload)
        telegram_sent = await self.notifier.send_message(formatted_msg)

        notif_log = NotificationLog(
            signal_id=signal.signal_id,
            channel="TELEGRAM",
            delivery_status="SENT" if telegram_sent else "PENDING_OR_MOCKED",
            payload=msg_payload,
            sent_at=datetime.utcnow() if telegram_sent else None
        )
        self.db.add(notif_log)
        self.db.commit()

        logger.info(f"Signal successfully published: {signal.signal_id} ({entry_type} {side})")
        return signal

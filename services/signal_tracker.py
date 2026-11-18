import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Any, List
from sqlalchemy.orm import Session

from database.models import Signal, SignalEvent, SignalEvaluation

logger = logging.getLogger(__name__)

class SignalTracker:
    def __init__(self, db: Session):
        self.db = db

    def update_all_signals(self, market: Dict[str, Any], current_time: datetime = None) -> List[Dict[str, Any]]:
        """Track active signals through their lifecycle according to Section 11 & 14.5."""
        now = current_time or datetime.utcnow()
        bid = Decimal(str(market.get("bid", 0.0)))
        ask = Decimal(str(market.get("ask", 0.0)))
        updated_events = []

        active_signals = self.db.query(Signal).filter(
            Signal.status.in_(["WAITING_FOR_ENTRY", "MONITORING", "PUBLISHED"])
        ).all()

        for sig in active_signals:
            # 1. Direct Limit: Waiting for entry touch
            if sig.status == "WAITING_FOR_ENTRY":
                # Check if target reached before entry touched (Missed Opportunity)
                if sig.side == "BUY" and bid >= sig.take_profit:
                    sig.status = "EXPIRED"
                    sig.closed_at = now
                    self._record_event(sig, "EXPIRED_TARGET_REACHED_BEFORE_ENTRY", bid)
                    self._record_eval(sig, "VALID_SETUP", "EXPIRED", "TP reached before entry limit was touched.")
                    updated_events.append({"signal_id": str(sig.signal_id), "status": "EXPIRED"})
                    continue
                elif sig.side == "SELL" and ask <= sig.take_profit:
                    sig.status = "EXPIRED"
                    sig.closed_at = now
                    self._record_event(sig, "EXPIRED_TARGET_REACHED_BEFORE_ENTRY", ask)
                    self._record_eval(sig, "VALID_SETUP", "EXPIRED", "TP reached before entry limit was touched.")
                    updated_events.append({"signal_id": str(sig.signal_id), "status": "EXPIRED"})
                    continue

                # Check touch (Opsi A - Direct Limit)
                touched = False
                touch_price = None
                if sig.entry_type == "BUY_LIMIT" and ask <= sig.entry_price:
                    touched = True
                    touch_price = ask
                elif sig.entry_type == "SELL_LIMIT" and bid >= sig.entry_price:
                    touched = True
                    touch_price = bid

                if touched:
                    sig.status = "MONITORING"
                    self._record_event(sig, "FILLED_SIMULATED", touch_price)
                    updated_events.append({"signal_id": str(sig.signal_id), "status": "FILLED_MONITORING"})

            # 2. Market Entry immediate transition to MONITORING
            elif sig.status == "PUBLISHED" and sig.entry_type == "MARKET":
                sig.status = "MONITORING"
                self._record_event(sig, "FILLED_MARKET", sig.entry_price)

            # 3. Monitoring filled signal for TP / SL
            if sig.status == "MONITORING":
                tp_hit = False
                sl_hit = False

                if sig.side == "BUY":
                    if bid >= sig.take_profit:
                        tp_hit = True
                    if bid <= sig.stop_loss:
                        sl_hit = True
                else:  # SELL
                    if ask <= sig.take_profit:
                        tp_hit = True
                    if ask >= sig.stop_loss:
                        sl_hit = True

                if tp_hit and sl_hit:
                    # Ambiguous resolution
                    sig.status = "AMBIGUOUS"
                    sig.closed_at = now
                    self._record_event(sig, "AMBIGUOUS_SPIKE", bid)
                    self._record_eval(sig, "VALID_SETUP", "AMBIGUOUS", "Both TP and SL hit during volatile spike.", r_mult=Decimal("0.0"))
                    updated_events.append({"signal_id": str(sig.signal_id), "status": "AMBIGUOUS"})
                elif tp_hit:
                    sig.status = "TP_HIT"
                    sig.closed_at = now
                    self._record_event(sig, "TP_HIT", sig.take_profit)
                    self._record_eval(sig, "VALID_SETUP", "TP_HIT", "Take Profit achieved.", r_mult=sig.risk_reward)
                    updated_events.append({"signal_id": str(sig.signal_id), "status": "TP_HIT"})
                elif sl_hit:
                    sig.status = "SL_HIT"
                    sig.closed_at = now
                    self._record_event(sig, "SL_HIT", sig.stop_loss)
                    self._record_eval(sig, "VALID_SETUP", "SL_HIT", "Stop Loss reached.", r_mult=Decimal("-1.0"))
                    updated_events.append({"signal_id": str(sig.signal_id), "status": "SL_HIT"})

        self.db.commit()
        return updated_events

    def _record_event(self, signal: Signal, event_type: str, price: Decimal):
        evt = SignalEvent(
            signal_id=signal.signal_id,
            event_type=event_type,
            timestamp_utc=datetime.utcnow(),
            price_at_event=price
        )
        self.db.add(evt)

    def _record_eval(self, signal: Signal, validity: str, outcome: str, notes: str, r_mult: Decimal = Decimal("0.0")):
        existing = self.db.query(SignalEvaluation).filter(SignalEvaluation.signal_id == signal.signal_id).first()
        if not existing:
            ev = SignalEvaluation(
                signal_id=signal.signal_id,
                setup_validity=validity,
                trade_outcome=outcome,
                analysis_quality={"evaluated_by": "auto_tracker"},
                r_multiple=r_mult,
                notes=notes,
                evaluated_at=datetime.utcnow()
            )
            self.db.add(ev)

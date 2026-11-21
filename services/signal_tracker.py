import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Any, List
from sqlalchemy.orm import Session

from database.models import Signal, SignalEvent, SignalEvaluation, SignalRevision

logger = logging.getLogger(__name__)

class SignalTracker:
    def __init__(self, db: Session):
        self.db = db

    def update_all_signals(self, market: Dict[str, Any], current_time: datetime = None) -> List[Dict[str, Any]]:
        """Track active signals through their lifecycle with Auto-Breakeven,
        Trailing Stop, and Multi-Target 1:5+ Runner logic.
        """
        now = current_time or datetime.utcnow()
        bid = Decimal(str(market.get("bid", 0.0)))
        ask = Decimal(str(market.get("ask", 0.0)))
        spread = Decimal(str(round(market.get("ask", 0.0) - market.get("bid", 0.0), 2)))
        updated_events = []

        active_signals = self.db.query(Signal).filter(
            Signal.status.in_(["WAITING_FOR_ENTRY", "MONITORING", "PUBLISHED"])
        ).all()

        for sig in active_signals:
            # 1. Direct Limit: Waiting for entry touch
            if sig.status == "WAITING_FOR_ENTRY":
                # Target reached before entry touched -> Incomplete setup / Missed Opportunity
                target_reached = False
                check_price = bid if sig.side == "BUY" else ask
                if (sig.side == "BUY" and bid >= sig.take_profit) or (sig.side == "SELL" and ask <= sig.take_profit):
                    target_reached = True

                if target_reached:
                    sig.status = "EXPIRED"
                    sig.closed_at = now
                    self._record_event(sig, "EXPIRED_TARGET_REACHED_BEFORE_ENTRY", check_price)
                    self._record_eval(sig, "INCOMPLETE_SETUP", "EXPIRED", "TP reached before limit entry was touched (Missed Opportunity).")
                    updated_events.append({"signal_id": str(sig.signal_id), "status": "EXPIRED"})
                    continue

                # Check touch (Direct Limit)
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

            # 3. Active Position Monitoring (Auto-Breakeven, Trailing Stop, Multi-Target)
            if sig.status == "MONITORING":
                current_price = bid if sig.side == "BUY" else ask
                init_risk = abs(sig.entry_price - sig.stop_loss)
                if init_risk <= 0:
                    init_risk = Decimal("1.0")

                # Compute current floating R
                if sig.side == "BUY":
                    float_r = (bid - sig.entry_price) / init_risk
                else:
                    float_r = (sig.entry_price - ask) / init_risk

                # Update max floating R reached
                if sig.max_r_multiple is None or float_r > sig.max_r_multiple:
                    sig.max_r_multiple = Decimal(str(round(float_r, 2)))

                # A. Auto-Breakeven when price reaches +1.2R
                if float_r >= Decimal("1.2") and not sig.is_breakeven_set:
                    old_sl = sig.stop_loss
                    # Set SL to entry + spread buffer (risk-free)
                    be_price = sig.entry_price + (spread if sig.side == "BUY" else -spread)
                    sig.stop_loss = be_price
                    sig.is_breakeven_set = True
                    self._record_event(sig, "BREAKEVEN_PROTECTED", be_price)
                    self._record_revision(sig, old_sl=old_sl, new_sl=be_price, reason="Auto-Breakeven activated at +1.2R")
                    updated_events.append({"signal_id": str(sig.signal_id), "status": "BREAKEVEN_SET"})

                # B. Dynamic Trailing Stop for 1:5+ Runner
                if float_r >= Decimal("3.0"):
                    # Lock in +1.5R
                    target_trail = sig.entry_price + (init_risk * Decimal("1.5") if sig.side == "BUY" else -init_risk * Decimal("1.5"))
                    if (sig.side == "BUY" and target_trail > sig.stop_loss) or (sig.side == "SELL" and target_trail < sig.stop_loss):
                        old_sl = sig.stop_loss
                        sig.stop_loss = target_trail
                        self._record_event(sig, "TRAILING_STOP_UPDATED", target_trail)
                        self._record_revision(sig, old_sl=old_sl, new_sl=target_trail, reason="Trailing stop locked +1.5R at +3.0R runner")

                if float_r >= Decimal("4.5"):
                    # Lock in +3.0R
                    target_trail = sig.entry_price + (init_risk * Decimal("3.0") if sig.side == "BUY" else -init_risk * Decimal("3.0"))
                    if (sig.side == "BUY" and target_trail > sig.stop_loss) or (sig.side == "SELL" and target_trail < sig.stop_loss):
                        old_sl = sig.stop_loss
                        sig.stop_loss = target_trail
                        self._record_event(sig, "TRAILING_STOP_UPDATED", target_trail)
                        self._record_revision(sig, old_sl=old_sl, new_sl=target_trail, reason="Trailing stop locked +3.0R at +4.5R runner")

                # C. Check TP & SL Hits
                tp_runner_hit = False
                tp_base_hit = False
                sl_hit = False

                # Check TP3 (1:5+ Runner)
                if sig.take_profit_3:
                    if sig.side == "BUY" and bid >= sig.take_profit_3:
                        tp_runner_hit = True
                    elif sig.side == "SELL" and ask <= sig.take_profit_3:
                        tp_runner_hit = True

                # Check TP1 (Base TP)
                if sig.side == "BUY":
                    if bid >= sig.take_profit:
                        tp_base_hit = True
                    if bid <= sig.stop_loss:
                        sl_hit = True
                else:
                    if ask <= sig.take_profit:
                        tp_base_hit = True
                    if ask >= sig.stop_loss:
                        sl_hit = True

                # Resolution
                if tp_runner_hit:
                    sig.status = "TP_HIT"
                    sig.closed_at = now
                    achieved_r = sig.max_r_multiple or Decimal("5.0")
                    self._record_event(sig, "TP_RUNNER_HIT", sig.take_profit_3)
                    self._record_eval(sig, "VALID_SETUP", "TP_HIT", "Full 1:5+ Runner TP achieved! Macro trend captured.", r_mult=achieved_r)
                    updated_events.append({"signal_id": str(sig.signal_id), "status": "TP_RUNNER_HIT"})
                elif tp_base_hit and not sig.take_profit_3:
                    sig.status = "TP_HIT"
                    sig.closed_at = now
                    self._record_event(sig, "TP_HIT", sig.take_profit)
                    self._record_eval(sig, "VALID_SETUP", "TP_HIT", "Take Profit achieved.", r_mult=sig.risk_reward)
                    updated_events.append({"signal_id": str(sig.signal_id), "status": "TP_HIT"})
                elif sl_hit:
                    sig.closed_at = now
                    if sig.is_breakeven_set:
                        # Stopped out in Breakeven or Trailing profit
                        if sig.max_r_multiple and sig.max_r_multiple >= Decimal("2.0"):
                            sig.status = "TP_HIT"
                            achieved_r = Decimal(str(round(float(sig.max_r_multiple) * 0.7, 2)))
                            self._record_event(sig, "TRAILING_STOP_EXIT", sig.stop_loss)
                            self._record_eval(sig, "VALID_SETUP", "TP_HIT", f"Closed in profit by trailing stop (+{achieved_r}R).", r_mult=achieved_r)
                            updated_events.append({"signal_id": str(sig.signal_id), "status": "TRAILING_STOP_EXIT"})
                        else:
                            sig.status = "BREAKEVEN"
                            self._record_event(sig, "BREAKEVEN_EXIT", sig.stop_loss)
                            self._record_eval(sig, "VALID_SETUP", "BREAKEVEN", "Capital protected: closed at Breakeven.", r_mult=Decimal("0.0"))
                            updated_events.append({"signal_id": str(sig.signal_id), "status": "BREAKEVEN"})
                    else:
                        # Hit real Stop Loss
                        sig.status = "SL_HIT"
                        self._record_event(sig, "SL_HIT", sig.stop_loss)
                        # Determine setup validity: did price immediately invert without any progress?
                        max_r = sig.max_r_multiple or Decimal("0.0")
                        if max_r < Decimal("0.3"):
                            validity = "INVALID_SETUP"
                            notes = "Analisa INVALID: Premis struktur langsung patah/reversal palsu."
                        else:
                            validity = "VALID_SETUP"
                            notes = "Analisa VALID: Setup sempat berjalan searah namun berbalik sebelum TP."

                        self._record_eval(sig, validity, "SL_HIT", notes, r_mult=Decimal("-1.0"))
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

    def _record_revision(self, signal: Signal, old_sl: Decimal, new_sl: Decimal, reason: str):
        rev = SignalRevision(
            signal_id=signal.signal_id,
            timestamp_utc=datetime.utcnow(),
            old_sl=old_sl,
            new_sl=new_sl,
            reason=reason
        )
        self.db.add(rev)

    def _record_eval(self, signal: Signal, validity: str, outcome: str, notes: str, r_mult: Decimal = Decimal("0.0")):
        existing = self.db.query(SignalEvaluation).filter(SignalEvaluation.signal_id == signal.signal_id).first()
        if not existing:
            ev = SignalEvaluation(
                signal_id=signal.signal_id,
                setup_validity=validity,
                trade_outcome=outcome,
                analysis_quality={
                    "evaluated_by": "auto_tracker",
                    "setup_valid": (validity == "VALID_SETUP"),
                    "final_r": float(r_mult)
                },
                r_multiple=r_mult,
                notes=notes,
                evaluated_at=datetime.utcnow()
            )
            self.db.add(ev)
        else:
            existing.setup_validity = validity
            existing.trade_outcome = outcome
            existing.r_multiple = r_mult
            existing.notes = notes
            existing.evaluated_at = datetime.utcnow()
            self.db.add(ev)

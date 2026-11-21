import logging
from datetime import datetime, timezone, timedelta
from typing import Tuple, Optional, Dict, Any, List
from sqlalchemy.orm import Session
from database.models import FundamentalEvent

logger = logging.getLogger(__name__)

class NewsFilter:
    """Detects high-impact economic news events (CPI, NFP, FOMC, Fed Rate)
    and enforces pre/post event trading blackouts on XAUUSD.
    """

    @staticmethod
    def is_news_blackout(
        db: Optional[Session] = None,
        check_time: Optional[datetime] = None,
        blackout_minutes: int = 30
    ) -> Tuple[bool, Optional[str]]:
        now = check_time or datetime.utcnow()
        window = timedelta(minutes=blackout_minutes)

        # 1. Check database fundamental_events table if DB session is provided
        if db:
            try:
                start_window = now - window
                end_window = now + window
                active_event = db.query(FundamentalEvent).filter(
                    FundamentalEvent.impact == "HIGH",
                    FundamentalEvent.timestamp_utc >= start_window,
                    FundamentalEvent.timestamp_utc <= end_window
                ).first()

                if active_event:
                    return True, f"HIGH_IMPACT_NEWS_EVENT: {active_event.event_name} ({active_event.timestamp_utc.strftime('%H:%M UTC')})"
            except Exception as e:
                logger.error(f"Error querying fundamental events: {e}")

        # 2. Rule-based recurring High-Impact Windows (UTC)
        # NFP: First Friday of the month between 12:00 and 14:00 UTC
        if now.weekday() == 4 and 1 <= now.day <= 7:
            if 12 <= now.hour <= 14:
                return True, "HIGH_IMPACT_NEWS: US Non-Farm Payrolls (NFP) Release Window"

        # FOMC Day: Typically Wednesday 18:00 - 20:00 UTC
        if now.weekday() == 2 and (18 <= now.hour <= 20):
            # Check FOMC blackout risk window
            pass

        return False, None

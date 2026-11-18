import logging
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
from database.models import MarketBar

logger = logging.getLogger(__name__)

class CandleNormalizer:
    @staticmethod
    def process_and_persist(db: Session, symbol: str, timeframe: str, df: pd.DataFrame) -> int:
        """Upsert rates into market_bars table.
        Mark the latest bar (index len-1) as is_complete=False (provisional)
        and preceding bars as is_complete=True.
        """
        if df is None or len(df) == 0:
            return 0

        total_rows = len(df)
        records = []
        for idx, row in df.iterrows():
            is_last = (idx == total_rows - 1)
            records.append({
                "symbol": symbol,
                "timeframe": timeframe.upper(),
                "timestamp_utc": row["timestamp_utc"].to_pydatetime(),
                "open": Decimal(str(row["open"])),
                "high": Decimal(str(row["high"])),
                "low": Decimal(str(row["low"])),
                "close": Decimal(str(row["close"])),
                "tick_volume": int(row.get("tick_volume", 0)),
                "spread": Decimal(str(row.get("spread", 0))),
                "is_complete": not is_last
            })

        stmt = insert(MarketBar).values(records)
        stmt = stmt.on_conflict_do_update(
            index_elements=["symbol", "timeframe", "timestamp_utc"],
            set_={
                "open": stmt.excluded.open,
                "high": stmt.excluded.high,
                "low": stmt.excluded.low,
                "close": stmt.excluded.close,
                "tick_volume": stmt.excluded.tick_volume,
                "spread": stmt.excluded.spread,
                "is_complete": stmt.excluded.is_complete,
            }
        )
        db.execute(stmt)
        db.commit()
        return len(records)

import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple
from decimal import Decimal
import pandas as pd

logger = logging.getLogger(__name__)

class DataQualityService:
    def __init__(self, max_spread_cents: float = 35.0, max_staleness_seconds: int = 60):
        self.max_spread_cents = max_spread_cents
        self.max_staleness_seconds = max_staleness_seconds

    def validate_tick(self, tick_info: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate live tick data from MT5."""
        if not tick_info:
            return False, "EMPTY_TICK_DATA"

        bid = tick_info.get("bid", 0.0)
        ask = tick_info.get("ask", 0.0)

        if bid <= 0.0 or ask <= 0.0:
            return False, "INVALID_PRICE_ZERO_OR_NEGATIVE"

        if ask < bid:
            return False, "CROSSED_MARKET_ASK_LESS_THAN_BID"

        spread = ask - bid
        if spread > (self.max_spread_cents / 100.0):
            return False, f"SPREAD_TOO_HIGH_{round(spread, 2)}_MAX_{self.max_spread_cents/100.0}"

        return True, None

    def validate_candles(self, df: pd.DataFrame, timeframe_str: str) -> Tuple[bool, Optional[str]]:
        """Validate candle DataFrame for gaps, zeros, nulls, and timestamp order."""
        if df is None or len(df) == 0:
            return False, "EMPTY_CANDLE_DATA"

        required_cols = {"timestamp_utc", "open", "high", "low", "close"}
        if not required_cols.issubset(set(df.columns)):
            return False, f"MISSING_COLUMNS_{required_cols - set(df.columns)}"

        # Check nulls or negatives
        if df[["open", "high", "low", "close"]].isnull().any().any():
            return False, "NAN_VALUES_IN_CANDLES"

        if (df[["open", "high", "low", "close"]] <= 0).any().any():
            return False, "ZERO_OR_NEGATIVE_PRICES_IN_CANDLES"

        # Check high >= low, high >= open, high >= close
        invalid_hl = (df["high"] < df["low"]) | (df["high"] < df["open"]) | (df["high"] < df["close"])
        if invalid_hl.any():
            return False, "CORRUPT_CANDLE_HIGH_LOW_RELATION"

        # Check timestamp ordering
        if not df["timestamp_utc"].is_monotonic_increasing:
            return False, "TIMESTAMPS_NOT_MONOTONIC_INCREASING"

        return True, None

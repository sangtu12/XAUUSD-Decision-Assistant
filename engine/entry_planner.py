import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class EntryPlanner:
    @staticmethod
    def choose_entry(setup: Dict[str, Any], market: Dict[str, Any], max_chase_points: float = 30.0) -> Optional[Dict[str, Any]]:
        """Selects between Market Entry and Direct Limit according to Section 10 & 14.3."""
        direction = setup.get("direction")
        market_plan = setup.get("market_plan")
        limit_plan = setup.get("limit_plan")
        current_bid = market.get("bid", 0.0)
        current_ask = market.get("ask", 0.0)

        # 1. Evaluate Market Plan
        if market_plan:
            ref_price = market_plan.get("reference_price", current_ask if direction == "BUY" else current_bid)
            entry_price = current_ask if direction == "BUY" else current_bid
            # Check chase tolerance
            chase = abs(entry_price - ref_price)
            if chase <= (max_chase_points / 100.0):
                # Price is still within fair entry zone
                market_plan["entry_price"] = entry_price
                market_plan["selected_type"] = "MARKET"
                return market_plan

        # 2. Evaluate Direct Limit Plan (Opsi A)
        if limit_plan:
            limit_entry = limit_plan.get("entry_price", 0.0)
            if direction == "BUY":
                # Buy Limit must be below current Ask
                if limit_entry < current_ask:
                    limit_plan["selected_type"] = "BUY_LIMIT"
                    return limit_plan
            else:
                # Sell Limit must be above current Bid
                if limit_entry > current_bid:
                    limit_plan["selected_type"] = "SELL_LIMIT"
                    return limit_plan

        return None

import logging
from typing import Dict, Any, Tuple
from config.settings import settings

logger = logging.getLogger(__name__)

class RiskEngine:
    @staticmethod
    def validate_plan(plan: Dict[str, Any], market: Dict[str, Any], regime: Dict[str, Any]) -> Tuple[bool, str]:
        """Validate an entry plan according to Section 14.4 of the Blueprint.
        Returns (is_valid, reason).
        """
        bid = market.get("bid", 0.0)
        ask = market.get("ask", 0.0)
        spread_cents = (ask - bid) * 100.0

        # 1. Spread Check
        if spread_cents > float(settings.MAX_SPREAD_CENTS):
            return False, f"SPREAD_EXCEEDS_MAX: {round(spread_cents, 1)} > {settings.MAX_SPREAD_CENTS}"

        # 2. Stop Loss & Take Profit presence
        entry = plan.get("entry_price")
        sl = plan.get("stop_loss")
        tp = plan.get("take_profit")
        if not entry or not sl or not tp:
            return False, "MISSING_ENTRY_SL_OR_TP"

        # 3. Risk and Reward distance
        risk_dist = abs(entry - sl)
        reward_dist = abs(tp - entry)
        if risk_dist <= 0:
            return False, "RISK_DISTANCE_ZERO_OR_NEGATIVE"

        # 4. Minimum Risk:Reward ratio
        rr = reward_dist / risk_dist
        if rr < float(settings.MIN_RISK_REWARD):
            return False, f"RISK_REWARD_BELOW_MINIMUM: {round(rr, 2)} < {settings.MIN_RISK_REWARD}"

        # 5. Maximum Stop Distance
        if risk_dist > (float(settings.MAX_STOP_DISTANCE_POINTS) / 100.0):
            return False, f"SL_DISTANCE_TOO_WIDE: {round(risk_dist, 2)}"

        # 6. Volatility Gate
        volatility = regime.get("volatility_regime", "NORMAL")
        if volatility == "EXTREME" and not settings.ALLOW_EXTREME_VOLATILITY:
            return False, "BLOCKED_BY_EXTREME_VOLATILITY_GATE"

        return True, "RISK_VALID"

import logging
from typing import Optional, Dict, Any
import httpx
from config.settings import settings

logger = logging.getLogger(__name__)

class TelegramNotifier:
    def __init__(self, token: Optional[str] = None, chat_id: Optional[str] = None):
        self.token = token or settings.TELEGRAM_BOT_TOKEN
        self.chat_id = chat_id or settings.TELEGRAM_CHAT_ID

    async def send_message(self, text: str) -> bool:
        if not self.token or not self.chat_id:
            logger.info(f"[Mock Telegram Dispatch] (Tokens not set in .env):\n{text}")
            return False

        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "Markdown"
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(url, json=payload)
                if res.status_code == 200:
                    logger.info("Telegram notification delivered successfully.")
                    return True
                else:
                    logger.error(f"Telegram API error {res.status_code}: {res.text}")
        except Exception as e:
            logger.warning(f"HTTPX error sending Telegram notification, using fallback: {e}")

        # Fallback to curl.exe for robust delivery on Windows environments
        try:
            import subprocess
            cmd = [
                "curl.exe", "-s", "-X", "POST", url,
                "-d", f"chat_id={self.chat_id}",
                "-d", f"text={text}",
                "-d", "parse_mode=Markdown"
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if '"ok":true' in res.stdout:
                logger.info("Telegram notification delivered successfully via curl fallback.")
                return True
            else:
                logger.error(f"Telegram curl fallback failed: {res.stdout}")
                return False
        except Exception as ex:
            logger.error(f"All Telegram delivery methods failed: {ex}")
            return False

    @staticmethod
    def format_signal_message(signal_data: Dict[str, Any]) -> str:
        order_type = signal_data.get("entry_type", "MARKET")
        side = signal_data.get("side", "BUY")
        icon = "🟢" if side == "BUY" else "🔴"
        
        msg = (
            f"*{icon} XAUUSD SIGNAL: {order_type} {side}*\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 *Strategy*: `{signal_data.get('strategy_name', 'Rule-Based')}`\n"
            f"📍 *Entry*: `{signal_data.get('entry_price', '0.0')}`\n"
            f"🛑 *Stop Loss*: `{signal_data.get('stop_loss', '0.0')}`\n"
            f"🏁 *Take Profit*: `{signal_data.get('take_profit', '0.0')}`\n"
            f"⚖️ *Risk/Reward*: `1:{signal_data.get('risk_reward', '2.0')}`\n"
            f"📊 *Spread*: `{signal_data.get('spread', 'N/A')}`\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 *Rationale*: {signal_data.get('rationale', 'N/A')}\n"
            f"⏳ *Expiry*: Dynamic (Premise broken or max lifetime cap)"
        )
        return msg

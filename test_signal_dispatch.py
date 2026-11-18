import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.connection import SessionLocal
from services.signal_publisher import SignalPublisher

async def main():
    print("Menguji pengiriman sinyal sampel ke Telegram dan Dashboard...")
    db = SessionLocal()
    try:
        publisher = SignalPublisher(db)

        # Setup sampel
        setup_data = {
            "strategy": "TrendFollowing",
            "direction": "SELL",
            "fingerprint": "DEMO_TEST_SIGNAL_001",
            "rationale": "Uji coba integrasi sistem: H1 Bearish bias + M15 Pullback EMA 20 rejection."
        }

        entry_plan = {
            "selected_type": "SELL_LIMIT",
            "entry_price": 3825.50,
            "stop_loss": 3832.00,
            "take_profit": 3812.50,
            "risk_reward": 2.0,
            "reference_price": 3823.50
        }

        regime_snapshot = {
            "trend_regime": "BEARISH_TREND",
            "volatility_regime": "NORMAL",
            "evidence": {"close": 3823.50, "ema_20": 3825.50, "ema_50": 3830.00}
        }

        market_data = {
            "bid": 3823.50,
            "ask": 3823.84,
            "spread": 34
        }

        sig = await publisher.publish_signal(
            setup_data=setup_data,
            entry_plan=entry_plan,
            features_snapshot={"ema_20": 3825.50, "rsi_14": 42.5},
            regime_snapshot=regime_snapshot,
            market_data=market_data
        )

        if sig:
            print(f"✅ Sinyal tes berhasil diterbitkan dengan ID: {sig.signal_id}")
            print(f"Cek Telegram kamu di t.me/trade_assistant_drkns_bot!")
        else:
            print("Sinyal dilewati (mungkin duplikat).")
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())

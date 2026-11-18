import logging
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import desc

from config.settings import settings
from database.connection import get_db, init_db
from database.models import Signal, SignalSnapshot, SignalEvent, SignalEvaluation, MarketBar
from engine.monitoring_loop import MonitoringEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("api")

app = FastAPI(
    title="XAUUSD Trading Decision Assistant API",
    version="0.3",
    description="Backend API and Realtime Stream for XAUUSD Decision Support System"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

# Mount static files and root dashboard
static_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
def serve_dashboard():
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "XAUUSD Trading Decision Assistant API Active. Access /docs for Swagger."}

# Shared Monitoring Engine
monitoring_engine = MonitoringEngine()

# WebSocket Connection Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: Dict[str, Any]):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(connection)

manager = ConnectionManager()

@app.on_event("startup")
async def on_startup():
    init_db()
    logger.info("Database initialized.")
    # Launch continuous background monitoring loop (5-sec interval)
    asyncio.create_task(monitoring_engine.start(poll_interval_sec=5))

@app.on_event("shutdown")
def on_shutdown():
    monitoring_engine.stop()

@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "mt5_initialized": monitoring_engine.mt5.initialized
    }

@app.get("/api/market/overview")
async def get_market_overview():
    if monitoring_engine.latest_state:
        return monitoring_engine.latest_state
    return await monitoring_engine.run_single_iteration()

@app.get("/api/market/candles")
def get_candles(timeframe: str = "M5", count: int = 100, db: Session = Depends(get_db)):
    bars = db.query(MarketBar).filter(
        MarketBar.timeframe == timeframe.upper()
    ).order_by(MarketBar.timestamp_utc.asc()).all()
    
    return [
        {
            "time": int(b.timestamp_utc.timestamp()),
            "open": float(b.open),
            "high": float(b.high),
            "low": float(b.low),
            "close": float(b.close),
            "volume": b.tick_volume,
            "is_complete": b.is_complete
        }
        for b in bars[-count:]
    ]

@app.get("/api/signals/active")
def get_active_signals(db: Session = Depends(get_db)):
    signals = db.query(Signal).filter(
        Signal.status.in_(["PUBLISHED", "WAITING_FOR_ENTRY", "MONITORING"])
    ).order_by(desc(Signal.published_at)).all()

    return [
        {
            "signal_id": str(s.signal_id),
            "entry_type": s.entry_type,
            "side": s.side,
            "reference_price": float(s.reference_price),
            "entry_price": float(s.entry_price),
            "stop_loss": float(s.stop_loss),
            "take_profit": float(s.take_profit),
            "risk_reward": float(s.risk_reward),
            "status": s.status,
            "published_at": s.published_at.isoformat() if s.published_at else None
        }
        for s in signals
    ]

@app.get("/api/signals/history")
def get_signal_history(limit: int = 50, db: Session = Depends(get_db)):
    signals = db.query(Signal).order_by(desc(Signal.published_at)).limit(limit).all()
    res = []
    for s in signals:
        eval_data = None
        if s.evaluation:
            eval_data = {
                "setup_validity": s.evaluation.setup_validity,
                "trade_outcome": s.evaluation.trade_outcome,
                "r_multiple": float(s.evaluation.r_multiple) if s.evaluation.r_multiple is not None else None,
                "notes": s.evaluation.notes
            }
        res.append({
            "signal_id": str(s.signal_id),
            "entry_type": s.entry_type,
            "side": s.side,
            "entry_price": float(s.entry_price),
            "stop_loss": float(s.stop_loss),
            "take_profit": float(s.take_profit),
            "risk_reward": float(s.risk_reward),
            "status": s.status,
            "published_at": s.published_at.isoformat() if s.published_at else None,
            "closed_at": s.closed_at.isoformat() if s.closed_at else None,
            "evaluation": eval_data
        })
    return res

@app.get("/api/signals/{signal_id}")
def get_signal_detail(signal_id: str, db: Session = Depends(get_db)):
    signal = db.query(Signal).filter(Signal.signal_id == signal_id).first()
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")

    snapshot = signal.snapshot.snapshot_data if signal.snapshot else None
    events = [
        {
            "event_type": e.event_type,
            "price": float(e.price_at_event) if e.price_at_event else None,
            "timestamp": e.timestamp_utc.isoformat(),
            "payload": e.payload
        }
        for e in signal.events
    ]
    return {
        "signal_id": str(signal.signal_id),
        "status": signal.status,
        "entry_type": signal.entry_type,
        "side": signal.side,
        "entry_price": float(signal.entry_price),
        "stop_loss": float(signal.stop_loss),
        "take_profit": float(signal.take_profit),
        "risk_reward": float(signal.risk_reward),
        "snapshot": snapshot,
        "events": events
    }

@app.get("/api/analytics")
def get_analytics(db: Session = Depends(get_db)):
    total_signals = db.query(Signal).count()
    tp_hits = db.query(Signal).filter(Signal.status == "TP_HIT").count()
    sl_hits = db.query(Signal).filter(Signal.status == "SL_HIT").count()
    expired = db.query(Signal).filter(Signal.status == "EXPIRED").count()
    filled = db.query(Signal).filter(Signal.status.in_(["MONITORING", "TP_HIT", "SL_HIT", "BREAKEVEN"])).count()

    win_rate = (tp_hits / (tp_hits + sl_hits) * 100.0) if (tp_hits + sl_hits) > 0 else 0.0

    return {
        "total_signals": total_signals,
        "tp_hits": tp_hits,
        "sl_hits": sl_hits,
        "expired": expired,
        "filled_signals": filled,
        "win_rate_percentage": round(win_rate, 2),
    }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Send live ping or receive client messages
            data = await websocket.receive_text()
            await websocket.send_json({"echo": data, "timestamp": datetime.utcnow().isoformat()})
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# XAUUSD Trading Decision Assistant (v0.3)

Aplikasi pendukung keputusan trading emas (*decision support system*) otomatis multi-timeframe berbasis **MetaTrader 5 (MT5)**, **Python FastAPI**, **PostgreSQL**, dan **TradingView Lightweight Charts**, mengacu pada dokumen spesifikasi arsitektur *Blueprint v0.3*.

---

## Fitur Utama

- **Autonomous Market Monitoring**: Memantau feed broker MT5 secara otomatis tanpa perlu intervensi manual.
- **Multi-Timeframe Engine**: Sinkronisasi data M5, M15, H1, dan H4 dalam waktu UTC.
- **3 Strategi Inti Terukur**:
  1. *Trend Following* (H4/H1 bias + M15 EMA pullback + M5 trigger).
  2. *Liquidity Sweep Reversal* (M15 Swing High/Low sweep & reclaim + M5 MSS).
  3. *Breakout & Retest* (H1 S/R breakout displacement + M15 retest).
- **Dual Entry Engine**: Mendukung *Market Entry* (chase tolerance validation) dan *Direct Limit* (Buy Limit / Sell Limit - Opsi A).
- **Gate Risiko Ketat**: Pemeriksaan spread dinamis, minimum Risk:Reward (1:1.5 - 1:2.0), dan volatilitas ekstrim.
- **Immutable Snapshots**: Setiap sinyal resmi dibekukan (*frozen*) bersama seluruh data indikator & harga saat publikasi untuk mencegah *lookahead bias*.
- **Evaluasi 3 Dimensi**: Pemisahan evaluasi antara *Setup Validity* (Valid/Invalid/Incomplete), *Trade Outcome* (TP/SL/BE/Expired/Ambiguous), dan *Analysis Quality*.
- **Notifikasi Instan**: Pengiriman sinyal terformat rapi ke Telegram Bot.
- **Modern Dark-Mode Dashboard**: Visualisasi chart real-time, ticker harga, active signals board, dan snapshot drawer di browser.

---

##  Struktur Proyek

```
xauusd-decision-assistant/
├── .venv/                      # Python 3.11 Virtual Environment
├── .env                        # Konfigurasi sistem, broker MT5, risk & Telegram
├── api/
│   └── main.py                 # FastAPI REST API, WebSocket & Web Dashboard server
├── collector/
│   ├── mt5_client.py           # MT5 API connection wrapper & auto-symbol discovery
│   ├── data_quality.py         # Validasi tick, spread, gaps, dan kelengkapan candle
│   └── candle_builder.py       # Multi-timeframe normalizer & PostgreSQL upsert
├── config/
│   └── settings.py             # Pydantic BaseSettings
├── database/
│   ├── connection.py           # SQLAlchemy PostgreSQL engine & session
│   └── models.py               # Schema 13 tabel (instruments, signals, snapshots, dll)
├── engine/
│   ├── feature_engine.py       # EMA, RSI, ATR, Swing Detection, Fair Value Gap (FVG)
│   ├── regime_detector.py      # Klasifikasi 2-sumbu: Arah & Volatilitas independen
│   ├── entry_planner.py        # Pemilihan Market Entry vs Buy/Sell Limit
│   ├── risk_engine.py          # Validasi spread, SL distance, RR, dan volatility gate
│   ├── monitoring_loop.py      # Siklus monitoring otomatis end-to-end
│   └── strategies/
│       ├── base.py
│       ├── trend_following.py
│       ├── liquidity_sweep.py
│       └── breakout_retest.py
├── services/
│   ├── signal_publisher.py     # Deduplikasi, pembuatan snapshot, dan event logger
│   ├── signal_tracker.py       # Pelacakan status sinyal (Filled, TP/SL, Expired)
│   └── telegram_notifier.py    # Pengiriman notifikasi ke Telegram channel/bot
└── static/
    └── index.html              # Frontend Dashboard (Tailwind + TradingView Charts)
```

---

##  Konfigurasi `.env`

File `.env` sudah disiapkan dengan nilai default:

```ini
# PostgreSQL
DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/xauusd_assistant

# MetaTrader 5
MT5_PATH=C:\Program Files\MetaTrader 5\terminal64.exe
MT5_SYMBOL=XAUUSD
MT5_TIMEFRAMES=M5,M15,H1,H4

# Risk & Gate Thresholds
MAX_SPREAD_CENTS=50.0
MIN_RISK_REWARD=1.5
MAX_STOP_DISTANCE_POINTS=500.0
ALLOW_EXTREME_VOLATILITY=false

# Telegram Notifikasi (Opsional untuk testing Telegram live)
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```

---

##  Menjalankan Aplikasi

1. **Jalankan Server Dashboard & API**:
   ```powershell
   .\.venv\Scripts\python.exe -m uvicorn api.main:app --app-dir . --host 127.0.0.1 --port 8000
   ```
2. **Buka Web Dashboard di Browser**:
   - Dashboard: `http://127.0.0.1:8000`
   - Dokumentasi Swagger API: `http://127.0.0.1:8000/docs`

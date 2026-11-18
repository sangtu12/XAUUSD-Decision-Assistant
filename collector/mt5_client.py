import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
import pandas as pd

logger = logging.getLogger(__name__)

# Timeframe mapping from string to MT5 timeframe constants
TIMEFRAME_MAP = {
    "M1": 1,
    "M5": 5,
    "M15": 15,
    "M30": 30,
    "H1": 16385,
    "H4": 16388,
    "D1": 16408,
}

class MT5Client:
    """Wrapper for MetaTrader 5 API with safe initialization, auto symbol discovery,
    and UTC time normalization.
    """
    def __init__(self, path: Optional[str] = None, login: Optional[int] = None, 
                 password: Optional[str] = None, server: Optional[str] = None):
        self.path = path
        self.login = login
        self.password = password
        self.server = server
        self.initialized = False
        self.active_symbol: Optional[str] = None
        self._mt5 = None

    def connect(self) -> bool:
        try:
            import MetaTrader5 as mt5
            self._mt5 = mt5
        except ImportError:
            logger.error("MetaTrader5 package is not installed.")
            return False

        init_kwargs = {}
        if self.path:
            init_kwargs["path"] = self.path
        if self.login:
            init_kwargs["login"] = int(self.login)
        if self.password:
            init_kwargs["password"] = self.password
        if self.server:
            init_kwargs["server"] = self.server

        logger.info(f"Connecting to MT5 with path: {self.path}...")
        self.initialized = self._mt5.initialize(**init_kwargs)
        if not self.initialized:
            error = self._mt5.last_error()
            logger.error(f"Failed to initialize MT5: {error}")
            return False

        terminal_info = self._mt5.terminal_info()
        logger.info(f"MT5 Connected successfully! Terminal: {terminal_info}")
        return True

    def find_gold_symbol(self, preferred_symbol: str = "XAUUSD") -> Optional[str]:
        """Auto-detect gold symbol in broker Market Watch (e.g. XAUUSD, XAUUSDm, GOLD, GOLDm)."""
        if not self.initialized or not self._mt5:
            return None

        # Try preferred first
        symbols = self._mt5.symbols_get()
        if not symbols:
            return None

        symbol_names = [s.name for s in symbols]
        candidates = [preferred_symbol, "XAUUSD", "GOLD", "XAUUSDm", "GOLDm", "XAUUSD.a", "GOLD.a", "XAUUSD_i"]
        
        for cand in candidates:
            if cand in symbol_names:
                # Ensure it's selected in Market Watch
                self._mt5.symbol_select(cand, True)
                self.active_symbol = cand
                logger.info(f"Selected Gold symbol in MT5: {cand}")
                return cand

        # Fallback: search substring
        for name in symbol_names:
            if "XAU" in name.upper() or "GOLD" in name.upper():
                self._mt5.symbol_select(name, True)
                self.active_symbol = name
                logger.info(f"Detected Gold symbol by search: {name}")
                return name

        logger.warning("Could not find any XAUUSD or GOLD symbol in MT5 symbols.")
        return None

    def get_symbol_info(self, symbol: Optional[str] = None) -> Optional[Dict[str, Any]]:
        if not self.initialized or not self._mt5:
            return None
        sym = symbol or self.active_symbol
        if not sym:
            return None

        info = self._mt5.symbol_info(sym)
        if info is None:
            return None

        return {
            "name": info.name,
            "bid": info.bid,
            "ask": info.ask,
            "spread": info.spread,  # in points
            "point": info.point,
            "digits": info.digits,
            "trade_tick_size": info.trade_tick_size,
            "trade_contract_size": info.trade_contract_size,
        }

    def fetch_rates(self, symbol: str, timeframe_str: str, count: int = 100) -> Optional[pd.DataFrame]:
        """Fetch OHLC rates. 
        Important: MT5 returns bar index -1 as current unclosed bar (or index 0 in descending order).
        We return a DataFrame with UTC timestamps.
        """
        if not self.initialized or not self._mt5:
            return None

        tf_const = TIMEFRAME_MAP.get(timeframe_str.upper())
        if tf_const is None:
            logger.error(f"Unsupported timeframe: {timeframe_str}")
            return None

        rates = self._mt5.copy_rates_from_pos(symbol, tf_const, 0, count)
        if rates is None or len(rates) == 0:
            logger.warning(f"No rates returned for {symbol} on {timeframe_str}: {self._mt5.last_error()}")
            return None

        df = pd.DataFrame(rates)
        # Convert timestamp to UTC datetime
        df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
        df.rename(columns={"time": "timestamp_utc", "real_volume": "real_vol"}, inplace=True)
        return df

    def disconnect(self):
        if self.initialized and self._mt5:
            self._mt5.shutdown()
            self.initialized = False
            logger.info("MT5 disconnected.")

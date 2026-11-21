import unittest
import sys
import os
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.backtest_engine import HistoricalBacktestEngine

class TestBacktestEngine(unittest.TestCase):
    def setUp(self):
        # Generate 150 synthetic candles
        times_m5 = [datetime(2026, 1, 1) + timedelta(minutes=5 * i) for i in range(150)]
        prices_m5 = [3500.0 + np.sin(i / 10.0) * 15.0 for i in range(150)]
        self.df_m5 = pd.DataFrame({
            "timestamp_utc": times_m5,
            "open": [p - 0.2 for p in prices_m5],
            "high": [p + 1.2 for p in prices_m5],
            "low": [p - 1.2 for p in prices_m5],
            "close": prices_m5,
            "tick_volume": [1200] * 150,
            "spread": [35] * 150
        })

        times_m15 = [datetime(2026, 1, 1) + timedelta(minutes=15 * i) for i in range(60)]
        prices_m15 = [3500.0 + np.sin(i / 4.0) * 15.0 for i in range(60)]
        self.df_m15 = pd.DataFrame({
            "timestamp_utc": times_m15,
            "open": [p - 0.5 for p in prices_m15],
            "high": [p + 2.0 for p in prices_m15],
            "low": [p - 2.0 for p in prices_m15],
            "close": prices_m15,
            "tick_volume": [3000] * 60,
            "spread": [35] * 60
        })

    def test_backtest_run(self):
        engine = HistoricalBacktestEngine()
        res = engine.run_backtest({
            "M5": self.df_m5,
            "M15": self.df_m15,
            "H1": self.df_m15,
            "H4": self.df_m15
        })

        self.assertNotIn("error", res)
        self.assertIn("total_trades", res)
        self.assertIn("win_rate_pct", res)
        self.assertIn("profit_factor", res)
        self.assertIn("net_r", res)

if __name__ == "__main__":
    unittest.main()

import unittest
import sys
import os
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.main import app

class TestAPIEndpoints(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health(self):
        res = self.client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("status", data)
        self.assertEqual(data["status"], "healthy")

    def test_market_overview(self):
        res = self.client.get("/api/market/overview")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("status", data)

    def test_candles(self):
        res = self.client.get("/api/market/candles?timeframe=M5&count=10")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIsInstance(data, list)

    def test_active_signals(self):
        res = self.client.get("/api/signals/active")
        self.assertEqual(res.status_code, 200)
        self.assertIsInstance(res.json(), list)

    def test_signal_history(self):
        res = self.client.get("/api/signals/history?limit=10")
        self.assertEqual(res.status_code, 200)
        self.assertIsInstance(res.json(), list)

    def test_analytics(self):
        res = self.client.get("/api/analytics")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("total_signals", data)
        self.assertIn("win_rate_percentage", data)

    def test_dashboard_serve(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)

if __name__ == "__main__":
    unittest.main()

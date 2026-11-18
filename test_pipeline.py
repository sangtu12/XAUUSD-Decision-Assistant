import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine.monitoring_loop import MonitoringEngine

async def main():
    print("Testing End-to-End Monitoring Pipeline cycle...")
    engine = MonitoringEngine()
    result = await engine.run_single_iteration()
    print("\n--- Pipeline Result ---")
    print(result)
    engine.stop()

if __name__ == "__main__":
    asyncio.run(main())

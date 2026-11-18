import sys
import MetaTrader5 as mt5

def main():
    if not mt5.initialize(path=r"C:\Program Files\MetaTrader 5\terminal64.exe"):
        print("Failed to initialize MT5")
        sys.exit(1)

    symbol = "XAUUSD"
    mt5.symbol_select(symbol, True)
    
    info = mt5.symbol_info(symbol)
    if info:
        print(f"Symbol: {info.name}")
        print(f"Bid: {info.bid}, Ask: {info.ask}")
        print(f"Spread (points): {info.spread}, Point: {info.point}, Digits: {info.digits}")
        print(f"Calculated spread in USD/cents: {round((info.ask - info.bid), info.digits)}")

    rates_m5 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 3)
    if rates_m5 is not None:
        print("\nLast 3 M5 Bars:")
        for r in rates_m5:
            print(f"Time: {r['time']}, O: {r['open']}, H: {r['high']}, L: {r['low']}, C: {r['close']}, TickVol: {r['tick_volume']}")

    mt5.shutdown()

if __name__ == "__main__":
    main()

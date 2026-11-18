import sys
import MetaTrader5 as mt5

def main():
    print(f"MetaTrader5 Python package version: {mt5.__version__}")
    
    # Attempt initialize
    initialized = mt5.initialize(path=r"C:\Program Files\MetaTrader 5\terminal64.exe")
    if not initialized:
        print(f"Failed to initialize MT5, error code: {mt5.last_error()}")
        sys.exit(1)

    print("Successfully connected to MetaTrader 5 Terminal!")
    term_info = mt5.terminal_info()
    if term_info:
        print(f"Terminal Name: {term_info.name}")
        print(f"Connected to broker: {term_info.connected}")
        print(f"Community account: {term_info.community_account}")
        print(f"Data path: {term_info.data_path}")

    # Check account info
    acc_info = mt5.account_info()
    if acc_info:
        print(f"Account Login: {acc_info.login}")
        print(f"Broker/Company: {acc_info.company}")
        print(f"Server: {acc_info.server}")
        print(f"Currency: {acc_info.currency}")
        print(f"Trade Mode: {acc_info.trade_mode}")
    else:
        print("No active account logged in or account info unavailable.")

    # Search for Gold/XAU symbols
    symbols = mt5.symbols_get()
    if symbols:
        gold_symbols = [s.name for s in symbols if "XAU" in s.name.upper() or "GOLD" in s.name.upper()]
        print(f"Available Gold symbols: {gold_symbols}")
        if gold_symbols:
            chosen = gold_symbols[0]
            mt5.symbol_select(chosen, True)
            tick = mt5.symbol_info_tick(chosen)
            if tick:
                print(f"Current tick for {chosen} -> Bid: {tick.bid}, Ask: {tick.ask}, Spread: {round(tick.ask - tick.bid, 2)}")
            rates = mt5.copy_rates_from_pos(chosen, mt5.TIMEFRAME_M5, 0, 5)
            if rates is not None:
                print(f"Successfully fetched {len(rates)} M5 bars for {chosen}!")
    else:
        print("No symbols retrieved.")

    mt5.shutdown()
    print("MT5 shutdown clean.")

if __name__ == "__main__":
    main()

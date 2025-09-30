import logging
from core import trade_manager  # 👈 Import the TradeManager instance from core.py

async def signal_callback(signal: dict, raw_message=None):
    """
    Called when a trading signal is parsed from Telegram.
    Automatically forwards it to the trading core.
    Example signal:
    {
        "currency_pair": "EUR/USD",
        "direction": "BUY",
        "entry_time": "14:30",
        "timeframe": "M1",
        "martingale_times": ["14:31", "14:32"]
    }
    """
    logging.info(f"[📩] New trading signal received: {signal}")

    try:
        # ✅ Forward signal directly to trading core
        trade_manager.handle_signal(signal)
        logging.info("[🤖] Signal forwarded to TradeManager for processing and scheduling.")
    except Exception as e:
        logging.error(f"[❌] Failed to forward signal to TradeManager: {e}")

async def command_callback(cmd: str):
    """
    Called when a command (/start or /stop) is received.
    """
    logging.info(f"[💻] Command received: {cmd}")

    try:
        # ✅ Forward commands to trading core (start/stop trading)
        trade_manager.handle_command(cmd)
    except Exception as e:
        logging.error(f"[❌] Failed to process command in TradeManager: {e}")

    if cmd.startswith("/start"):
        logging.info("[✅] Start command received — trading enabled.")
    elif cmd.startswith("/stop"):
        logging.info("[🛑] Stop command received — trading disabled.")
        

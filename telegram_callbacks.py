# telegram_callbacks.py
import logging
from datetime import datetime

async def signal_callback(signal: dict, raw_message: str = None):
    """
    Called when a trading signal is parsed from Telegram.
    Logs the parsed signal and the time it was received.
    
    Example signal dict:
    {
        "currency_pair": "EUR/USD",
        "direction": "BUY",
        "entry_time": "14:30",
        "timeframe": "M1",
        "martingale_times": ["14:31", "14:32"]
    }
    """
    received_time = datetime.utcnow().strftime("%H:%M:%S")
    logging.info(f"[📩] Signal received at {received_time}: {signal}")

async def command_callback(cmd: str):
    """
    Called when a command (/start or /stop) is received.
    """
    logging.info(f"[💻] Command received: {cmd}")

    if cmd.startswith("/start"):
        logging.info("[✅] Start command received — you could enable trading here.")
    elif cmd.startswith("/stop"):
        logging.info("[🛑] Stop command received — you could disable trading here.")
        

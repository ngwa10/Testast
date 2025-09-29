# telegram_callbacks.py
import logging

async def signal_callback(signal: dict):
    """
    Called when a trading signal is parsed from Telegram.
    The 'signal' dict might look like:
    {
        "currency_pair": "EUR/USD",
        "direction": "BUY",
        "entry_time": "14:30",
        "timeframe": "M1",
        "martingale_times": ["14:31", "14:32"]
    }
    """
    logging.info(f"[📩] New trading signal received: {signal}")

async def command_callback(cmd: str):
    """
    Called when a command (/start or /stop) is received.
    """
    logging.info(f"[💻] Command received: {cmd}")

    if cmd.startswith("/start"):
        logging.info("[✅] Start command received — you could enable trading here.")
    elif cmd.startswith("/stop"):
        logging.info("[🛑] Stop command received — you could disable trading here.")

# screen_logic.py
import logging

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%H:%M:%S'
)

def select_currency(currency):
    logging.info(f"[ℹ️] screen_logic received currency selection request: {currency}")
    # Stub: do nothing for now

def select_timeframe(timeframe):
    logging.info(f"[ℹ️] screen_logic received timeframe selection request: {timeframe}")
    # Stub: do nothing for now


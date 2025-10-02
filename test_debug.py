import asyncio
import logging
from datetime import datetime, timedelta
import pytz

from core import trade_manager, signal_callback

logging.basicConfig(level=logging.DEBUG,
                    format='[%(asctime)s] %(levelname)s: %(message)s',
                    datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)

async def main():
    # Construct a dummy signal to test your existing code
    tz = pytz.timezone("Africa/Douala")
    now = datetime.now(tz)
    signal = {
        "currency_pair": "AUD/CHF",
        "direction": "BUY",
        "entry_time": now + timedelta(seconds=10),  # schedule 10s from now
        "timeframe": "M5",
        "martingale_times": [
            now + timedelta(seconds=20),
            now + timedelta(seconds=30),
            now + timedelta(seconds=40)
        ],
        "source": "DebugTest"
    }

    logger.info("[🐞 DEBUG] Sending test signal to TradeManager...")
    await signal_callback(signal)
    logger.info("[🐞 DEBUG] Signal sent. Check logs for step-by-step actions.")

if __name__ == "__main__":
    asyncio.run(main())
  

import traceback
import core

try:
    # Prevent immediate crash by not initializing Selenium on startup
    trade_manager = core.trade_manager
    print("[✅] TradeManager instantiated successfully.")
except Exception:
    print("[❌] Exception during initialization:")
    traceback.print_exc()

# Keep container alive to inspect logs
import time
while True:
    time.sleep(1)
  

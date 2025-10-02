
# PocketOption Auto-Trader

Automated trading bot for PocketOption using Python, Selenium, and PyAutoGUI with VNC/NoVNC for GUI interaction and optional Telegram control. Includes robust dashboard verification and monitoring.

---

## Table of Contents

- [Features](#features)
- [Project Structure](#project-structure)
- [Requirements](#requirements)
- [Setup & Docker](#setup--docker)
- [Usage](#usage)
  - [Normal Start](#normal-start)
  - [Debug Mode](#debug-mode)
- [VNC / NoVNC](#vnc--novnc)
- [Trading & Signals](#trading--signals)
- [Logs & Monitoring](#logs--monitoring)
- [Notes](#notes)

---

## Features

- Fully automated PocketOption trading.
- Hotkey mode using PyAutoGUI for real UI interaction.
- Handles base trades and martingale strategy.
- Dashboard detection & login verification.
- Selenium monitors trade results in real-time.
- Telegram listener for commands (`/start`, `/stop`, `/status`).
- Runs headless or with a VNC desktop for visual verification.

---

## Project Structure

```

/
├─ core.py                  # TradeManager & main orchestration
├─ selenium_integration.py  # Selenium wrapper for PocketOption
├─ telegram_listener.py     # Telegram integration
├─ telegram_callbacks.py    # Command handling
├─ core_utils.py            # Utility functions
├─ debug_core.py            # Optional debug entrypoint
├─ start.sh                 # Start bot normally with VNC
├─ start_debug.sh           # Start bot for debugging & verification
├─ Dockerfile               # Container setup
├─ logs.json                # Optional log messages
├─ .env                     # Environment variables

````

---

## Requirements

- Docker (for containerized deployment)
- Linux or macOS host (Windows requires WSL or equivalent)
- Python 3.10+
- VNC / NoVNC dependencies installed in container

---

## Setup & Docker

Build the Docker image:

```bash
docker build -t pocketoption-bot .
````

Run the container:

```bash
docker run -it --rm -p 5901:5901 -p 6080:6080 pocketoption-bot
```

* `5901` → VNC port
* `6080` → NoVNC web client

---

## Usage

### Normal Start (`start.sh`)

Starts all services:

* VNC server
* NoVNC
* Telegram listener
* Core bot (trade manager + selenium)

```bash
chmod +x start.sh
./start.sh
```

The core bot will execute trades automatically when signals are received.

### Debug Mode (`start_debug.sh`)

Starts a virtual desktop and Selenium for monitoring and testing:

* Verifies dashboard login
* Reports balances and readiness
* Does not execute real trades if headless

```bash
chmod +x start_debug.sh
./start_debug.sh
```

---

## VNC / NoVNC

* **VNC server** allows viewing the virtual desktop running Xvfb.
* **NoVNC** provides browser access to the VNC desktop.
* Useful for monitoring Selenium interactions and handling manual CAPTCHA login if needed.

Access in browser: `http://<host-ip>:6080`

---

## Trading & Signals

* Signals are dictionaries containing:

```python
{
    "currency_pair": "CADUSD",
    "direction": "BUY" | "SELL",
    "entry_time": datetime.datetime(..., tzinfo=pytz.UTC),
    "timeframe": "M1" | "M5",
    "martingale_times": [datetime1, datetime2, ...]
}
```

* Core schedules trades and passes them to Selenium.
* Martingale levels are handled automatically with optional hotkey increases.
* Selenium watches for trade results and reports back to Core.

---

## Logs & Monitoring

* Logging is configured in `core.py`.
* `logs.json` can provide random messages for debugging and monitoring.
* Dashboard verification logs are produced in debug mode to confirm Selenium sees the trading interface.
* Max retries and wait times prevent false positives on login or dashboard detection.

---

## Notes

* **Credentials:** Hardcoded in `selenium_integration.py`. Ensure `.env` or secure storage for production use.
* **Chromedriver:** Path `/usr/local/bin/chromedriver`. Update if needed.
* **Headless:** Set `headless=True` in Selenium for no GUI.
* **Hotkey Mode:** Required for pyautogui-based interactions.
* **Retries:** Dashboard detection retries 3 times with 3-minute wait before confirming login.
* **CAPTCHA:** Manual intervention may be required on login; use VNC/NoVNC to complete if prompted.

---

## Contributing

1. Fork repository.
2. Update Selenium interactions or trade logic.
3. Test with `start_debug.sh`.
4. Submit PR with descriptive notes on changes.

---

## License

MIT License

```

This README now documents:  

- Both `start.sh` and `start_debug.sh`.  
- Docker setup.  
- VNC + NoVNC usage.  
- Core-Selenium architecture.  
- Trading, martingale, and signal handling.  
- Login/dashboard verification and logging.  

I can also draft a **diagram showing how Core, Selenium, Telegram, and VNC interact** for your README if you want it more visual. Do you want me to do that?
```

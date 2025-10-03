#!/bin/bash
set -e

# -------------------------
# Environment
# -------------------------
export DISPLAY=:1
export VNC_RESOLUTION=${VNC_RESOLUTION:-1280x800}
export NO_VNC_HOME=${NO_VNC_HOME:-/opt/noVNC}

# -------------------------
# Start virtual display (Xvfb)
# -------------------------
echo "[ℹ️] Starting Xvfb..."
Xvfb :1 -screen 0 ${VNC_RESOLUTION}x24 &
XVFB_PID=$!
sleep 5
echo "[✅] Xvfb started with DISPLAY=$DISPLAY (PID=$XVFB_PID)"

# -------------------------
# Optional: start noVNC (if you need web access)
# -------------------------
if [ -d "$NO_VNC_HOME" ]; then
    echo "[ℹ️] Starting noVNC..."
    ${NO_VNC_HOME}/utils/novnc_proxy --vnc localhost:5901 --listen 6080 &
    echo "[✅] noVNC started on port 6080"
fi

# -------------------------
# Launch Chrome as dockuser
# -------------------------
echo "[ℹ️] Launching Chrome..."
google-chrome-stable \
    --no-sandbox \
    --disable-setuid-sandbox \
    --disable-gpu \
    --disable-dev-shm-usage \
    --disable-blink-features=AutomationControlled \
    --user-data-dir=/home/dockuser/chrome-profile \
    --start-maximized \
    http://pocketoption.com/en/login/ &
CHROME_PID=$!
sleep 5
echo "[✅] Chrome launched (PID=$CHROME_PID)"

# -------------------------
# Start Python scripts
# -------------------------
echo "[ℹ️] Starting Python scripts..."
python3 -u telegram_listener.py >> /home/dockuser/telegram.log 2>&1 &
python3 -u screen_logic.py >> /home/dockuser/screen_logic.log 2>&1 &
echo "[✅] Python scripts started in background"

# -------------------------
# Start core bot loop
# -------------------------
while true; do
    echo "[ℹ️] Starting core bot..."
    python3 -u core.py >> /home/dockuser/core.log 2>&1
    EXIT_CODE=$?
    if [ $EXIT_CODE -ne 0 ]; then
        echo "[⚠️] Core bot crashed with exit code $EXIT_CODE, restarting in 5s..."
        sleep 5
    else
        echo "[ℹ️] Core bot finished normally."
        break
    fi
done

# -------------------------
# Clean up on exit
# -------------------------
echo "[ℹ️] Stopping Xvfb..."
kill $XVFB_PID || true
echo "[✅] Done."

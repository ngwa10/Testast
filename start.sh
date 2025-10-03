#!/bin/bash
set -e

# -------------------------
# Environment
# -------------------------
export DISPLAY=:1
export NO_VNC_HOME=/opt/noVNC
export VNC_RESOLUTION=${VNC_RESOLUTION:-1280x800}

# -------------------------
# Start VNC server
# -------------------------
vncserver :1 -geometry ${VNC_RESOLUTION} -depth 24 -SecurityTypes None
echo "[✅] VNC server started on :1 with resolution ${VNC_RESOLUTION} (passwordless)"

# -------------------------
# Start noVNC
# -------------------------
${NO_VNC_HOME}/utils/novnc_proxy --vnc localhost:5901 --listen 6080 &
echo "[✅] noVNC started on port 6080"

# -------------------------
# Wait for display to be ready
# -------------------------
sleep 5

# -------------------------
# Launch Chrome for Selenium / manual login
# -------------------------
echo "[ℹ️] Launching Chrome..."
google-chrome-stable \
    --no-sandbox \
    --disable-gpu \
    --disable-dev-shm-usage \
    --disable-blink-features=AutomationControlled \
    --user-data-dir=/home/dockuser/chrome-profile \
    --start-maximized \
    http://pocketoption.com/en/login/ &
sleep 5
echo "[✅] Chrome launched"

# -------------------------
# Start Telegram listener
# -------------------------
python3 -u telegram_listener.py &
echo "[ℹ️] Telegram listener started in background"

# -------------------------
# Start screen logic (Selenium + screen detection)
# -------------------------
python3 -u screen_logic.py &
echo "[ℹ️] screen_logic started in background"

# -------------------------
# Start core bot (production)
# -------------------------
while true; do
    echo "[ℹ️] Starting core bot..."
    python3 -u core.py
    exit_code=$?
    if [ $exit_code -ne 0 ]; then
        echo "[⚠️] Core bot exited unexpectedly with code $exit_code. Restarting in 5 seconds..."
        sleep 5
    else
        echo "[ℹ️] Core bot finished normally."
        break
    fi
done

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
echo "[✅] VNC server started on :1 with resolution ${VNC_RESOLUTION}"

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
# Launch Chrome (non-root)
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
sleep 5
echo "[✅] Chrome launched"

# -------------------------
# Start Python scripts
# -------------------------
python3 -u telegram_listener.py >> /home/dockuser/telegram.log 2>&1 &
python3 -u screen_logic.py >> /home/dockuser/screen_logic.log 2>&1 &
echo "[ℹ️] Python scripts started in background"

# -------------------------
# Start core bot loop
# -------------------------
while true; do
    echo "[ℹ️] Starting core bot..."
    python3 -u core.py >> /home/dockuser/core.log 2>&1
    exit_code=$?
    if [ $exit_code -ne 0 ]; then
        echo "[⚠️] Core bot exited with code $exit_code. Restarting in 5 seconds..."
        sleep 5
    else
        echo "[ℹ️] Core bot finished normally."
        break
    fi
done

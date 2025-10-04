#!/bin/bash
set -e

# -------------------------
# Environment
# -------------------------
export DISPLAY=:1
export NO_VNC_HOME=/opt/noVNC
export VNC_RESOLUTION=${VNC_RESOLUTION:-1280x800}

# -------------------------
# Start DBus
# -------------------------
eval $(dbus-launch --sh-syntax)
echo "[ℹ️] DBus session started"

# -------------------------
# Start VNC server
# -------------------------
vncserver :1 -geometry ${VNC_RESOLUTION} -depth 24 -SecurityTypes None
echo "[✅] VNC server started on :1 with resolution ${VNC_RESOLUTION}"

# -------------------------
# Start noVNC (Zeabur-compatible port 8080)
# -------------------------
${NO_VNC_HOME}/utils/novnc_proxy --vnc localhost:5901 --listen 8080 &
echo "[✅] noVNC started on port 8080"

# -------------------------
# Start Telegram listener
# -------------------------
python3 -u telegram_listener.py &
echo "[ℹ️] Telegram listener started in background"

# -------------------------
# Start core bot in loop
# -------------------------
while true; do
    echo "[ℹ️] Starting core bot..."
    python3 -u core.py
    echo "[⚠️] Core bot exited unexpectedly. Restarting in 5 seconds..."
    sleep 5
done

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
echo "[ℹ️] Starting VNC server..."
vncserver $DISPLAY -geometry ${VNC_RESOLUTION} -depth 24 -SecurityTypes None
echo "[✅] VNC server started on $DISPLAY with resolution ${VNC_RESOLUTION}"

# -------------------------
# Start noVNC
# -------------------------
echo "[ℹ️] Starting noVNC proxy..."
${NO_VNC_HOME}/utils/novnc_proxy --vnc localhost:5901 --listen 8080 &
echo "[✅] noVNC started on port 8080 (access via http://<your-domain>:8080)"

# -------------------------
# Start Telegram listener
# -------------------------
echo "[ℹ️] Starting Telegram listener..."
python3 -u telegram_listener.py &
echo "[✅] Telegram listener started"

# -------------------------
# Start core bot in loop
# -------------------------
while true; do
    echo "[ℹ️] Starting core bot..."
    python3 -u core.py || true
    echo "[⚠️] Core bot exited unexpectedly. Restarting in 5 seconds..."
    sleep 5
done

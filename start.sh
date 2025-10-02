#!/bin/bash
set -e

# -------------------------
# Environment
# -------------------------
export DISPLAY=:1
export NO_VNC_HOME=/opt/noVNC
export VNC_RESOLUTION=${VNC_RESOLUTION:-1280x800}

# -------------------------
# Start VNC server (passwordless)
# -------------------------
vncserver :1 -geometry ${VNC_RESOLUTION} -depth 24 -SecurityTypes None
echo "[✅] VNC server started on :1 with resolution ${VNC_RESOLUTION} (passwordless)"

# -------------------------
# Start noVNC
# -------------------------
${NO_VNC_HOME}/utils/novnc_proxy --vnc localhost:5901 --listen 6080 &
echo "[✅] noVNC started on port 6080"

# -------------------------
# Give VNC a moment to start
# -------------------------
sleep 5

# -------------------------
# Start Python bot in persistent loop
# -------------------------
while true; do
    echo "[ℹ️] Starting bot..."
    python3 -u core.py
    echo "[⚠️] Bot exited unexpectedly. Restarting in 5 seconds..."
    sleep 5
done

#!/bin/bash
set -e

# -------------------------
# Start VNC server
# -------------------------
vncserver :1 -geometry ${VNC_RESOLUTION} -depth 24
echo "[✅] VNC server started on :1 with resolution ${VNC_RESOLUTION}"

# -------------------------
# Start noVNC
# -------------------------
${NO_VNC_HOME}/utils/novnc_proxy --vnc localhost:5901 --listen 6080 &
echo "[✅] noVNC started on port 6080"

# -------------------------
# Wait a few seconds for display
# -------------------------
sleep 3

# -------------------------
# Start Python bot
# -------------------------
exec python3 -u core.py

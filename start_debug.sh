#!/bin/bash
set -e

# -------------------------
# Environment
# -------------------------
export DISPLAY=:1
export NO_VNC_HOME=/opt/noVNC
export VNC_RESOLUTION=${VNC_RESOLUTION:-1280x800}

# -------------------------
# Start virtual display (Xvfb)
# -------------------------
Xvfb :1 -screen 0 ${VNC_RESOLUTION}x24 &
echo "[INFO] Virtual display Xvfb started on :1"

# -------------------------
# Start noVNC for viewing
# -------------------------
${NO_VNC_HOME}/utils/novnc_proxy --vnc localhost:5901 --listen 6080 &
echo "[INFO] noVNC started on port 6080"

sleep 5

# -------------------------
# Run debug script
# -------------------------
python3 -u debug_core.py

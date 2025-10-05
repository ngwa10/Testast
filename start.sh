#!/usr/bin/env bash
set -ex

# Environment variables
DISPLAY=${DISPLAY:-:1}
VNC_RESOLUTION=${VNC_RESOLUTION:-1280x800}
NO_VNC_HOME=${NO_VNC_HOME:-/opt/noVNC}
VNC_PORT=5901
NO_VNC_PORT=6080

echo "Starting XFCE desktop with VNC (no password) and noVNC..."

# Start X virtual framebuffer
Xvfb $DISPLAY -screen 0 ${VNC_RESOLUTION}x24 &

# Start XFCE
startxfce4 &

# Start VNC server without password
vncserver $DISPLAY -geometry $VNC_RESOLUTION -depth 24 -SecurityTypes None

# Start noVNC
$NO_VNC_HOME/utils/novnc_proxy --vnc localhost:$VNC_PORT --listen $NO_VNC_PORT &

# Keep container alive
tail -f /dev/null

#!/usr/bin/env bash
set -e

# --------- Config ---------
export DISPLAY=${DISPLAY:-:1}
export VNC_RESOLUTION=${VNC_RESOLUTION:-1280x800}
export NO_VNC_HOME=${NO_VNC_HOME:-/opt/noVNC}
export VNC_PORT=5901
export NO_VNC_PORT=6080

echo "✅ Starting XFCE Desktop with VNC (no password) and noVNC..."
echo "📺 Display: $DISPLAY"
echo "📐 Resolution: $VNC_RESOLUTION"
echo "🔌 VNC Port: $VNC_PORT"
echo "🌐 noVNC Port: $NO_VNC_PORT"

# --------- Start Xvfb ---------
echo "🚀 Starting virtual framebuffer (Xvfb)..."
Xvfb $DISPLAY -screen 0 ${VNC_RESOLUTION}x24 &

# --------- Start XFCE ---------
echo "🖥️  Starting XFCE4 Desktop..."
startxfce4 &

# --------- Start VNC server (no password) ---------
echo "📡 Starting TigerVNC server (no password)..."
vncserver $DISPLAY -geometry $VNC_RESOLUTION -depth 24 -SecurityTypes None

# --------- Start noVNC ---------
echo "🌍 Starting noVNC web client..."
$NO_VNC_HOME/utils/novnc_proxy --vnc localhost:$VNC_PORT --listen $NO_VNC_PORT &

# --------- Info ---------
echo "✅ VNC server running on: vnc://<container-ip>:$VNC_PORT (no password)"
echo "✅ noVNC web UI available at: http://localhost:$NO_VNC_PORT/vnc.html"

# --------- Keep container alive ---------
echo "📦 Container is now running. Press Ctrl+C to stop."
tail -f /dev/null

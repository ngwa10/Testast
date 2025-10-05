#!/bin/bash
set -e

# --------------------------
# Simple healthcheck script
# --------------------------

# Check VNC server
if ! pgrep -f "Xvnc\|vncserver" > /dev/null; then
    echo "[❌] VNC server not running"
    exit 1
else
    echo "[✅] VNC server is running"
fi

# Check noVNC/websockify
if ! pgrep -f "websockify" > /dev/null; then
    echo "[❌] noVNC/websockify not running"
    exit 1
else
    echo "[✅] noVNC/websockify is running"
fi

echo "[ℹ️] All services healthy"
exit 0

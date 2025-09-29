#!/bin/bash

# Simple healthcheck script
# Check if VNC server is running
if ! pgrep -f "Xvnc\|vncserver" > /dev/null; then
    echo "VNC server not running"
    exit 1
fi

# Check if noVNC/websockify is running  
if ! pgrep -f "websockify" > /dev/null; then
    echo "noVNC/websockify not running"
    exit 1
fi

echo "Services are healthy"
exit 0

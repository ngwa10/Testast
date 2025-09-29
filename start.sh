#!/bin/bash
set -e

# Setup
mkdir -p /home/dockuser/.vnc /home/dockuser/chrome-profile
chmod 700 /home/dockuser/.vnc

# Create xstartup
cat > /home/dockuser/.vnc/xstartup << 'EOF'
#!/bin/bash
export XKL_XMODMAP_DISABLE=1
exec startxfce4
EOF
chmod +x /home/dockuser/.vnc/xstartup

# Start VNC
echo "Starting VNC server..."
vncserver :1 -geometry 1280x800 -depth 24 -SecurityTypes None

# Start noVNC
echo "Starting noVNC..."
cd /opt/noVNC
/opt/noVNC/utils/websockify/run 6080 localhost:5901 --web /opt/noVNC &

# Wait for desktop
sleep 5

# Start Chrome
echo "Starting Chrome..."
export DISPLAY=:1
google-chrome-stable --no-sandbox --disable-dev-shm-usage --disable-gpu \
  --user-data-dir=/home/dockuser/chrome-profile \
  --start-maximized "https://pocketoption.com/login" &

# Keep running
echo "All services started. Container ready!"
tail -f /dev/null

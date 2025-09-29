#!/bin/bash
set -e

# Setup directories
mkdir -p /home/dockuser/.vnc /home/dockuser/chrome-profile
chmod 700 /home/dockuser/.vnc

# Create xstartup script.
cat > /home/dockuser/.vnc/xstartup << 'EOF'
#!/bin/bash
export XKL_XMODMAP_DISABLE=1
exec startxfce4
EOF
chmod +x /home/dockuser/.vnc/xstartup

# Start VNC server
echo "Starting VNC server..."
vncserver :1 -geometry 1280x800 -depth 24 -SecurityTypes None

# Start noVNC
echo "Starting noVNC..."
cd /opt/noVNC
/opt/noVNC/utils/websockify/run 6080 localhost:5901 --web /opt/noVNC &

# Give the desktop some time to start
sleep 5

# Optional: clear Chrome profile if you want a fresh session each time
# rm -rf /home/dockuser/chrome-profile/*

# Start Chrome and open PocketOption login page
echo "Starting Chrome with PocketOption login..."
export DISPLAY=:1
google-chrome-stable "https://pocketoption.com/login" \
  --new-window \
  --no-sandbox \
  --disable-dev-shm-usage \
  --disable-gpu \
  --start-maximized \
  --user-data-dir=/home/dockuser/chrome-profile &

# Keep the container running
echo "All services started. Container ready!"
tail -f /dev/null

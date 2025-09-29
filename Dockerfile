FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive \
    DISPLAY=:1 \
    VNC_RESOLUTION=1280x800 \
    NO_VNC_HOME=/opt/noVNC

# Install minimal packages first
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl wget ca-certificates gnupg2 \
    python3 git \
    && rm -rf /var/lib/apt/lists/*

# Install Chrome (separate step to avoid timeout)
RUN curl -fsSL https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list

RUN apt-get update && apt-get install -y --no-install-recommends \
    google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Install VNC and desktop (minimal XFCE)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tigervnc-standalone-server \
    xfce4-session xfce4-panel \
    xfce4-terminal \
    dbus-x11 \
    procps dos2unix \
    && rm -rf /var/lib/apt/lists/*

# Install noVNC
RUN git clone --depth 1 --branch v1.4.0 https://github.com/novnc/noVNC.git ${NO_VNC_HOME} \
    && git clone --depth 1 https://github.com/novnc/websockify.git ${NO_VNC_HOME}/utils/websockify \
    && chmod +x ${NO_VNC_HOME}/utils/websockify/run

# Create user
RUN useradd -m -s /bin/bash -u 1000 dockuser \
    && mkdir -p /home/dockuser/.vnc /home/dockuser/chrome-profile \
    && chown -R dockuser:dockuser /home/dockuser

# Copy start script
COPY start.sh /usr/local/bin/start.sh
RUN dos2unix /usr/local/bin/start.sh && chmod +x /usr/local/bin/start.sh

EXPOSE 5901 6080

USER dockuser
WORKDIR /home/dockuser

ENTRYPOINT ["/usr/local/bin/start.sh"]

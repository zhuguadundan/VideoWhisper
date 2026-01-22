#!/bin/bash
set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}VideoWhisper Docker Container Starting...${NC}"
echo -e "${BLUE}======================================${NC}"

# Check config
echo -e "${YELLOW}Checking configuration...${NC}"
if [ ! -f "/app/config.yaml" ]; then
    echo -e "${RED}config.yaml not found!${NC}"
    echo -e "${YELLOW}Please mount your config.yaml file or create one based on template.${NC}"
    echo -e "${YELLOW}   Example: docker run -v /host/path/config.yaml:/app/config.yaml${NC}"
    exit 1
else
    echo -e "${GREEN}Configuration file found${NC}"
fi

# Prepare dirs and permissions
echo -e "${YELLOW}Checking directories and permissions...${NC}"
mkdir -p /app/temp /app/output /app/logs /app/config
if [ ! -f "/app/temp/.task_history.json" ]; then
    echo '[]' > /app/temp/.task_history.json
    chmod 644 /app/temp/.task_history.json
fi
chmod 755 /app/temp /app/output /app/logs /app/config 2>/dev/null || true
echo -e "${GREEN}Directories and permissions ready${NC}"

# Storage info
echo -e "${BLUE}Storage Structure:${NC}"
echo -e "${BLUE}   - Output: /app/output (persistent results)${NC}"
echo -e "${BLUE}   - Temp: /app/temp (latest 3 tasks only)${NC}"
echo -e "${BLUE}   - Logs: /app/logs${NC}"
echo -e "${BLUE}   - Config: /app/config${NC}"

# FFmpeg
echo -e "${YELLOW}Checking FFmpeg...${NC}"
if command -v ffmpeg &> /dev/null; then
    FFMPEG_VERSION=$(ffmpeg -version | head -n 1 | cut -d ' ' -f 3)
    echo -e "${GREEN}FFmpeg $FFMPEG_VERSION is available${NC}"
else
    echo -e "${RED}FFmpeg not found!${NC}"
    exit 1
fi

# Python
echo -e "${YELLOW}Checking Python environment...${NC}"
python --version
echo -e "${GREEN}Python environment ready${NC}"

# System info
echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}System Information:${NC}"
echo -e "${BLUE}   - Python: $(python --version)${NC}"
echo -e "${BLUE}   - FFmpeg: $FFMPEG_VERSION${NC}"
echo -e "${BLUE}   - Working Directory: $(pwd)${NC}"
echo -e "${BLUE}   - Container User: $(whoami)${NC}"
echo -e "${BLUE}======================================${NC}"

# HTTPS settings
HTTPS_ENABLED=${HTTPS_ENABLED:-true}
HTTPS_PORT=${HTTPS_PORT:-5443}
echo -e "${GREEN}HTTP interface:  http://localhost:5000${NC}"
if [ "$HTTPS_ENABLED" = "true" ]; then
  echo -e "${GREEN}HTTPS interface: https://localhost:${HTTPS_PORT}${NC}"
  echo -e "${YELLOW}Note: HTTPS uses self-signed certificate, browser may show security warning${NC}"
fi

if [ "$HTTPS_ENABLED" = "true" ]; then
    echo -e "${YELLOW}Checking SSL certificates...${NC}"
    if [ -f "/app/config/cert.pem" ] && [ -f "/app/config/key.pem" ]; then
        echo -e "${GREEN}SSL certificates found${NC}"
    else
        echo -e "${YELLOW}SSL certificates not found, will be auto-generated${NC}"
    fi
fi

echo -e "${GREEN}Starting VideoWhisper Application...${NC}"
echo -e "${BLUE}======================================${NC}"

# If HTTPS is enabled, ensure certs and start stunnel as TLS terminator
if [ "$HTTPS_ENABLED" = "true" ]; then
  echo -e "${YELLOW}Ensuring SSL certificate exists before HTTPS start...${NC}"
  python - <<'PY'
from app.config.settings import Config
from app.utils.certificate_manager import CertificateManager
cfg = Config.get_https_config()
mgr = CertificateManager(cfg)
ok = mgr.ensure_certificates()
print('cert_ready:', ok)
PY

  # Build combined PEM for stunnel: prefer fullchain.pem if present
  if [ -f "/app/config/fullchain.pem" ] && [ -f "/app/config/key.pem" ]; then
    cat /app/config/key.pem /app/config/fullchain.pem > /app/config/stunnel.pem || true
  elif [ -f "/app/config/cert.pem" ] && [ -f "/app/config/key.pem" ]; then
    cat /app/config/key.pem /app/config/cert.pem > /app/config/stunnel.pem || true
  chmod 600 /app/config/stunnel.pem || true
  fi

  echo -e "${GREEN}Starting TLS terminator (stunnel) on :${HTTPS_PORT}${NC}"
  cat > /app/stunnel.conf <<STUNNEL
setuid = nobody
setgid = nogroup
foreground = yes
debug = info
pid = /tmp/stunnel.pid
client = no

[videowhisper-https]
accept = 0.0.0.0:${HTTPS_PORT}
connect = 127.0.0.1:5000
cert = /app/config/stunnel.pem
options = NO_SSLv2
options = NO_SSLv3
options = NO_TLSv1
# options = NO_TLSv1.1  # Removed: illegal in newer stunnel/OpenSSL; leaving it breaks HTTPS startup
STUNNEL

  if command -v stunnel >/dev/null 2>&1; then
    # 确保 stunnel.pem 存在且非空
    if [ ! -s "/app/config/stunnel.pem" ]; then
      echo -e "${RED}stunnel.pem 不存在或为空，无法启动 HTTPS${NC}"
      exit 1
    fi
    stunnel /app/stunnel.conf &
  elif command -v stunnel4 >/dev/null 2>&1; then
    if [ ! -s "/app/config/stunnel.pem" ]; then
      echo -e "${RED}stunnel.pem 不存在或为空，无法启动 HTTPS${NC}"
      exit 1
    fi
    stunnel4 /app/stunnel.conf &
  else
    echo -e "${RED}stunnel not found; HTTPS requested but unavailable${NC}"
    exit 1
  fi
fi

# Start single Gunicorn (HTTP)
echo -e "${GREEN}Starting HTTP on :5000${NC}"

# Concurrency defaults (memory-first); configurable via env
WORKER_CLASS=${GUNICORN_WORKER_CLASS:-gthread}
WORKERS=${GUNICORN_WORKERS:-1}
THREADS=${GUNICORN_THREADS:-2}
TIMEOUT=${GUNICORN_TIMEOUT:-120}

if [ "$WORKER_CLASS" = "gthread" ]; then
  THREAD_ARGS="--threads ${THREADS}"
else
  THREAD_ARGS=""
fi

exec gunicorn \
  --worker-class "$WORKER_CLASS" \
  --workers "$WORKERS" \
  ${THREAD_ARGS} \
  -t "$TIMEOUT" \
  -b 0.0.0.0:5000 \
  --access-logfile - \
  --error-logfile - \
  "app:create_app()"

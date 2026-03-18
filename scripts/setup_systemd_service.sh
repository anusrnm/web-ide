#!/bin/bash
# Setup script for the Web IDE systemd service on Linux/Raspberry Pi
# Run with: sudo bash scripts/setup_systemd_service.sh

set -e

echo "Setup Web IDE Service"
echo "====================="
echo ""

if [[ $EUID -ne 0 ]]; then
    echo "This script must be run as root. Use: sudo bash scripts/setup_systemd_service.sh"
    exit 1
fi

read -r -p "Enter project path (default: /home/pi/web-ide): " PROJECT_PATH
PROJECT_PATH=${PROJECT_PATH:-/home/pi/web-ide}

if [[ ! -d "$PROJECT_PATH" ]]; then
    echo "Directory does not exist: $PROJECT_PATH"
    exit 1
fi

if [[ ! -f "$PROJECT_PATH/app.py" ]]; then
    echo "app.py not found in: $PROJECT_PATH"
    exit 1
fi

read -r -p "Enter service name (default: webide): " SERVICE_NAME
SERVICE_NAME=${SERVICE_NAME:-webide}

read -r -p "Enter service user (default: pi): " SERVICE_USER
SERVICE_USER=${SERVICE_USER:-pi}

read -r -p "Enter Python path (default: /usr/bin/python3): " PYTHON_BIN
PYTHON_BIN=${PYTHON_BIN:-/usr/bin/python3}

if [[ ! -x "$PYTHON_BIN" ]]; then
    echo "Python executable not found: $PYTHON_BIN"
    exit 1
fi

read -r -p "Enter HOST (default: 0.0.0.0): " HOST
HOST=${HOST:-0.0.0.0}

read -r -p "Enter PORT (default: 5000): " PORT
PORT=${PORT:-5000}

read -r -p "Enter ROOT_DIR (default: $PROJECT_PATH): " ROOT_DIR
ROOT_DIR=${ROOT_DIR:-$PROJECT_PATH}

read -r -p "Enter WEBIDE_PASSWORD_HASH: " WEBIDE_PASSWORD_HASH
if [[ -z "$WEBIDE_PASSWORD_HASH" ]]; then
    echo "WEBIDE_PASSWORD_HASH cannot be empty"
    exit 1
fi

read -r -p "Enter SECRET_KEY: " SECRET_KEY
if [[ -z "$SECRET_KEY" ]]; then
    echo "SECRET_KEY cannot be empty"
    exit 1
fi

read -r -p "Enable secure session cookies (SESSION_COOKIE_SECURE, default: 0): " SESSION_COOKIE_SECURE
SESSION_COOKIE_SECURE=${SESSION_COOKIE_SECURE:-0}

ENV_FILE="/etc/${SERVICE_NAME}.env"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
SERVICE_UNIT="${SERVICE_NAME}.service"

echo ""
echo "Creating environment file at $ENV_FILE"

cat > "$ENV_FILE" << EOF
WEBIDE_PASSWORD_HASH=$WEBIDE_PASSWORD_HASH
SECRET_KEY=$SECRET_KEY
ROOT_DIR=$ROOT_DIR
HOST=$HOST
PORT=$PORT
SESSION_COOKIE_SECURE=$SESSION_COOKIE_SECURE
EOF

chmod 600 "$ENV_FILE"

echo "Creating service file at $SERVICE_FILE"

cat > "$SERVICE_FILE" << EOF
[Unit]
Description=Web IDE Service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=$PROJECT_PATH
EnvironmentFile=$ENV_FILE
ExecStart=$PYTHON_BIN $PROJECT_PATH/app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

echo "Reloading systemd daemon"
systemctl daemon-reload

echo "Enabling $SERVICE_UNIT"
systemctl enable "$SERVICE_UNIT"

echo "Starting $SERVICE_UNIT"
systemctl restart "$SERVICE_UNIT"

echo ""
echo "Service status:"
systemctl status "$SERVICE_UNIT" --no-pager

echo ""
echo "Useful commands:"
echo "  sudo journalctl -u $SERVICE_NAME -f"
echo "  sudo systemctl restart $SERVICE_NAME"
echo "  sudo systemctl stop $SERVICE_NAME"
echo "  sudo systemctl disable $SERVICE_NAME"

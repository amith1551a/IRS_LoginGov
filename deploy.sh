#!/usr/bin/env bash
# Deploy IRIS Etel IAM Demo on Amazon Linux 2/2023 for an existing nginx setup.
set -euo pipefail

APP_DIR="/opt/iris-etel"
DOMAIN="etelligent-group.dev"
SERVICE_USER="ec2-user"

# Ensure required environment variables are set before running.
: "${OIDC_CLIENT_ID:?OIDC_CLIENT_ID is required}"
: "${SESSION_SECRET:?SESSION_SECRET is required}"

echo "==> Installing system dependencies"
sudo yum update -y
sudo yum install -y python3 python3-pip python3-venv git

echo "==> Creating application directory"
sudo mkdir -p "${APP_DIR}"
sudo chown "${SERVICE_USER}:${SERVICE_USER}" "${APP_DIR}"

# Copy application files from the current repo location.
# Adjust the source path if you are deploying from a different location.
echo "==> Copying application files"
rsync -av --exclude='venv' --exclude='.git' \
    "$(pwd)/" "${APP_DIR}/"

echo "==> Creating Python virtual environment"
python3 -m venv "${APP_DIR}/venv"
"${APP_DIR}/venv/bin/pip" install --upgrade pip
"${APP_DIR}/venv/bin/pip" install -r "${APP_DIR}/requirements.txt"

echo "==> Writing environment file"
cat > "${APP_DIR}/.env" <<EOF
OIDC_ISSUER=https://${DOMAIN}:8083
OIDC_CLIENT_ID=${OIDC_CLIENT_ID}
OIDC_REDIRECT_URI=https://${DOMAIN}/iam-demo/auth/callback
OIDC_POST_LOGOUT_URI=https://${DOMAIN}/iam-demo/auth/callback
SESSION_SECRET=${SESSION_SECRET}
APP_HOST=127.0.0.1
APP_PORT=8088
APP_ROOT_PATH=/iam-demo
EOF

echo "==> Deployment complete"
echo "Application: https://${DOMAIN}/iam-demo/"
echo "ZITADEL:     https://${DOMAIN}:8083/zitadel"
echo "Start the app with your existing process manager on 127.0.0.1:8088."
echo "Configure existing nginx to proxy /iam-demo/ to http://127.0.0.1:8088/."

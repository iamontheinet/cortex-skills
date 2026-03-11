#!/usr/bin/env bash
#
# Bootstrap script for Snowpipe Streaming Python project.
#
# What it does:
#   1. Creates a Python virtual environment (if not present)
#   2. Installs dependencies from requirements.txt
#   3. Generates RSA key pair (if not present)
#   4. Copies template configs (if no filled-in configs exist)
#
# Usage:
#   cd <project_root>
#   bash setup.sh
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${SCRIPT_DIR}/.venv"
KEY_FILE="${SCRIPT_DIR}/streaming_key.p8"
PUB_FILE="${SCRIPT_DIR}/streaming_key.pub"

echo "=== Snowpipe Streaming Python — Setup ==="

# --- 1. Virtual environment ---
if [ ! -d "${VENV_DIR}" ]; then
    echo "[1/4] Creating virtual environment..."
    python3 -m venv "${VENV_DIR}"
else
    echo "[1/4] Virtual environment already exists."
fi

echo "[2/4] Installing dependencies..."
"${VENV_DIR}/bin/pip" install --quiet --upgrade pip
"${VENV_DIR}/bin/pip" install --quiet -r "${SCRIPT_DIR}/requirements.txt"
echo "       Installed: $(${VENV_DIR}/bin/pip show snowpipe-streaming 2>/dev/null | grep Version || echo 'snowpipe-streaming not found')"

# --- 2. RSA key pair ---
if [ ! -f "${KEY_FILE}" ]; then
    echo "[3/4] Generating RSA key pair..."
    openssl genrsa 2048 2>/dev/null | openssl pkcs8 -topk8 -inform PEM -out "${KEY_FILE}" -nocrypt
    openssl rsa -in "${KEY_FILE}" -pubout -out "${PUB_FILE}" 2>/dev/null
    chmod 600 "${KEY_FILE}"
    echo "       Private key: ${KEY_FILE}"
    echo "       Public key:  ${PUB_FILE}"
    echo ""
    echo "  *** IMPORTANT: Register the public key with your Snowflake user ***"
    echo "  Run this SQL in Snowflake (replace <USERNAME>):"
    echo ""
    PUB_BODY=$(grep -v '^\-\-\-' "${PUB_FILE}" | tr -d '\n')
    echo "    ALTER USER <USERNAME> SET RSA_PUBLIC_KEY='${PUB_BODY}';"
    echo ""
else
    echo "[3/4] RSA key pair already exists."
fi

# --- 3. Config files ---
COPIED=false
if [ ! -f "${SCRIPT_DIR}/profile.json" ]; then
    cp "${SCRIPT_DIR}/profile.template.json" "${SCRIPT_DIR}/profile.json"
    echo "[4/4] Copied profile.template.json -> profile.json"
    echo "       *** Edit profile.json with your Snowflake credentials ***"
    COPIED=true
else
    echo "[4/4] profile.json already exists."
fi

if [ ! -f "${SCRIPT_DIR}/config.properties" ]; then
    cp "${SCRIPT_DIR}/config.template.properties" "${SCRIPT_DIR}/config.properties"
    if [ "$COPIED" = false ]; then
        echo "       Copied config.template.properties -> config.properties"
    else
        echo "       Copied config.template.properties -> config.properties"
    fi
fi

echo ""
echo "=== Setup complete ==="
echo ""
echo "Next steps:"
echo "  1. Edit profile.json with your Snowflake account details"
echo "  2. Register the RSA public key with your Snowflake user (if new)"
echo "  3. Create target tables in Snowflake (see SKILL.md)"
echo "  4. Run:  ${VENV_DIR}/bin/python src/streaming_app.py 1000"
echo ""

#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# setup.sh – initialise the dev container environment
# Run automatically via postCreateCommand in devcontainer.json
# ---------------------------------------------------------------------------
set -euo pipefail

WORKSPACE="${WORKSPACE:-/workspace}"
CONFIG_DIR="${WORKSPACE}/config"
DEVCONTAINER_CONFIG="${WORKSPACE}/.devcontainer/configuration.yaml"
HA_CONFIG="${CONFIG_DIR}/configuration.yaml"

echo "──────────────────────────────────────────"
echo " Duepi EVO – Container initialisation"
echo "──────────────────────────────────────────"

# 1. Install Python packages
echo "[1/3] Installing Python packages from requirements_test.txt …"
pip install --user -r "${WORKSPACE}/requirements_test.txt"

# 2. Create the Home Assistant config directory
echo "[2/3] Creating HA config directory at ${CONFIG_DIR} …"
mkdir -p "${CONFIG_DIR}"

# 3. Symlink .devcontainer/configuration.yaml → config/configuration.yaml
echo "[3/3] Linking ${DEVCONTAINER_CONFIG} → ${HA_CONFIG} …"
if [ -L "${HA_CONFIG}" ]; then
    echo "      Symlink already exists, skipping."
elif [ -f "${HA_CONFIG}" ]; then
    echo "      WARNING: ${HA_CONFIG} is a regular file, skipping symlink creation."
    echo "      Remove it manually and re-run this script if you want the symlink."
else
    ln -sf "${DEVCONTAINER_CONFIG}" "${HA_CONFIG}"
    echo "      Symlink created."
fi

echo ""
echo "✔ Setup complete. Happy coding!"

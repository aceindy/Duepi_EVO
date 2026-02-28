#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# setup.sh – initialise the dev container environment
# Run automatically via postCreateCommand in devcontainer.json
# ---------------------------------------------------------------------------
set -euo pipefail
set -x

WORKSPACE="/workspaces/Duepi_EVO"
SCRIPT_DIR="${WORKSPACE}/scripts"
CONFIG_DIR="${WORKSPACE}/config"
DEVCONTAINER_CONFIG="${WORKSPACE}/.devcontainer/configuration.yaml"
HA_CONFIG="${CONFIG_DIR}/configuration.yaml"
CUSTOM_COMPONENTS_SRC="${WORKSPACE}/custom_components/duepi_evo"
CUSTOM_COMPONENTS_DST="${CONFIG_DIR}/custom_components/duepi_evo"

echo "──────────────────────────────────────────"
echo " Duepi EVO – Container initialisation"
echo "──────────────────────────────────────────"

# 1. Install Python packages
echo "[1/4] Installing Python packages from requirements_test.txt …"
pip install --user -r "${WORKSPACE}/requirements_test.txt"

# 2. Create the Home Assistant config directory
echo "[2/4] Creating HA config directory at ${CONFIG_DIR} …"
mkdir -p "${CONFIG_DIR}"
chmod -R 777 "${CONFIG_DIR}"

# 3. Symlink .devcontainer/configuration.yaml → config/configuration.yaml
echo "[3/4] Linking ${DEVCONTAINER_CONFIG} → ${HA_CONFIG} …"
if [ -L "${HA_CONFIG}" ]; then
    echo "      Symlink already exists, skipping."
elif [ -f "${HA_CONFIG}" ]; then
    echo "      WARNING: ${HA_CONFIG} is a regular file, skipping symlink creation."
    echo "      Remove it manually and re-run this script if you want the symlink."
else
    ln -sf "${DEVCONTAINER_CONFIG}" "${HA_CONFIG}"
    echo "      Symlink created."
fi

# 4. Symlink custom_components/duepi_evo → config/custom_components/duepi_evo
echo "[4/4] Linking ${CUSTOM_COMPONENTS_SRC} → ${CUSTOM_COMPONENTS_DST} …"
mkdir -p "${CONFIG_DIR}/custom_components"
if [ -L "${CUSTOM_COMPONENTS_DST}" ]; then
    echo "      Symlink already exists, skipping."
elif [ -d "${CUSTOM_COMPONENTS_DST}" ]; then
    echo "      WARNING: ${CUSTOM_COMPONENTS_DST} is a real directory, skipping symlink creation."
    echo "      Remove it manually and re-run this script if you want the symlink."
else
    ln -sf "${CUSTOM_COMPONENTS_SRC}" "${CUSTOM_COMPONENTS_DST}"
    echo "      Symlink created."
fi

echo ""
echo "✔ Setup complete. Happy coding!"

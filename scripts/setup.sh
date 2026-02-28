#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# setup.sh – initialise the dev container environment
# Run automatically via postCreateCommand in devcontainer.json
# ---------------------------------------------------------------------------
set -euo pipefail
set -x

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_WORKSPACE="$(cd "${SCRIPT_DIR}/.." && pwd)"
WORKSPACE="${WORKSPACE:-${DEFAULT_WORKSPACE}}"
CONFIG_DIR="${WORKSPACE}/config"
DEVCONTAINER_CONFIG="${WORKSPACE}/.devcontainer/configuration.yaml"
HA_CONFIG="${CONFIG_DIR}/configuration.yaml"
CUSTOM_COMPONENTS_SRC="${WORKSPACE}/custom_components/duepi_evo"
CUSTOM_COMPONENTS_DST="${CONFIG_DIR}/custom_components/duepi_evo"
LOVELACE_DASHBOARDS_SRC="${WORKSPACE}/.devcontainer/lovelace_dashboards"
LOVELACE_DASHBOARDS_DST="${CONFIG_DIR}/.storage/lovelace_dashboards"
LOVELACE_DASHBOARD_TEST_SRC="${WORKSPACE}/.devcontainer/lovelace.dashboard_test"
LOVELACE_DASHBOARD_TEST_DST="${CONFIG_DIR}/.storage/lovelace.dashboard_test"
REQUIREMENTS_FILE="${WORKSPACE}/requirements_test.txt"
VENV_DIR="${WORKSPACE}/.venv"
MIN_PYTHON_VERSION="3.13.2"
VENV_PYTHON="${VENV_DIR}/bin/python"

if [ ! -d "${WORKSPACE}" ]; then
    echo "ERROR: WORKSPACE does not exist: ${WORKSPACE}" >&2
    exit 1
fi

if [ ! -f "${REQUIREMENTS_FILE}" ]; then
    echo "ERROR: requirements file not found: ${REQUIREMENTS_FILE}" >&2
    exit 1
fi

if [ ! -f "${DEVCONTAINER_CONFIG}" ]; then
    echo "ERROR: devcontainer configuration not found: ${DEVCONTAINER_CONFIG}" >&2
    exit 1
fi

if [ ! -d "${CUSTOM_COMPONENTS_SRC}" ]; then
    echo "ERROR: component source directory not found: ${CUSTOM_COMPONENTS_SRC}" >&2
    exit 1
fi

echo "──────────────────────────────────────────"
echo " Duepi EVO – Container initialisation"
echo "──────────────────────────────────────────"

# 1. Install Python packages
echo "[1/6] Creating/using virtualenv at ${VENV_DIR} and installing requirements …"
if [ ! -d "${VENV_DIR}" ] || [ ! -x "${VENV_PYTHON}" ]; then
    rm -rf "${VENV_DIR}"
    python3 -m venv "${VENV_DIR}"
fi
if ! "${VENV_PYTHON}" - <<'PY'
import sys
min_version = (3, 13, 2)
raise SystemExit(0 if sys.version_info >= min_version else 1)
PY
then
    echo "      Existing virtualenv Python is too old, recreating ${VENV_DIR}."
    rm -rf "${VENV_DIR}"
    python3 -m venv "${VENV_DIR}"
fi
export PATH="${VENV_DIR}/bin:${PATH}"
"${VENV_PYTHON}" - <<'PY'
import sys
min_version = (3, 13, 2)
if sys.version_info < min_version:
    raise SystemExit(
        f"ERROR: Python >= {'.'.join(map(str, min_version))} is required, "
        f"found {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}."
    )
PY
"${VENV_PYTHON}" -m pip install --upgrade pip
"${VENV_PYTHON}" -m pip install -r "${REQUIREMENTS_FILE}"

# 2. Create the Home Assistant config directory
echo "[2/6] Creating HA config directory at ${CONFIG_DIR} …"
mkdir -p "${CONFIG_DIR}"
chmod -R 777 "${CONFIG_DIR}"

# 3. Symlink .devcontainer/configuration.yaml → config/configuration.yaml
echo "[3/6] Linking ${DEVCONTAINER_CONFIG} → ${HA_CONFIG} …"
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
echo "[4/6] Linking ${CUSTOM_COMPONENTS_SRC} → ${CUSTOM_COMPONENTS_DST} …"
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

# 5. Symlink .devcontainer/lovelace_dashboards → config/.storage/lovelace_dashboards
echo "[5/6] Linking ${LOVELACE_DASHBOARDS_SRC} → ${LOVELACE_DASHBOARDS_DST} …"
mkdir -p "${CONFIG_DIR}/.storage"
if [ -L "${LOVELACE_DASHBOARDS_DST}" ]; then
    echo "      Symlink already exists, skipping."
elif [ -f "${LOVELACE_DASHBOARDS_DST}" ]; then
    echo "      WARNING: ${LOVELACE_DASHBOARDS_DST} is a regular file, skipping symlink creation."
    echo "      Remove it manually and re-run this script if you want the symlink."
else
    ln -sf "${LOVELACE_DASHBOARDS_SRC}" "${LOVELACE_DASHBOARDS_DST}"
    echo "      Symlink created."
fi

# 6. Symlink .devcontainer/lovelace.dashboard_test → config/.storage/lovelace.dashboard_test
echo "[6/6] Linking ${LOVELACE_DASHBOARD_TEST_SRC} → ${LOVELACE_DASHBOARD_TEST_DST} …"
if [ -L "${LOVELACE_DASHBOARD_TEST_DST}" ]; then
    echo "      Symlink already exists, skipping."
elif [ -f "${LOVELACE_DASHBOARD_TEST_DST}" ]; then
    echo "      WARNING: ${LOVELACE_DASHBOARD_TEST_DST} is a regular file, skipping symlink creation."
    echo "      Remove it manually and re-run this script if you want the symlink."
else
    ln -sf "${LOVELACE_DASHBOARD_TEST_SRC}" "${LOVELACE_DASHBOARD_TEST_DST}"
    echo "      Symlink created."
fi

echo ""
echo "✔ Setup complete. Happy coding!"

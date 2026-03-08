#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# ha.sh – Helper script to manage the Home Assistant dev instance
#
# Usage:
#   ./scripts/ha.sh start    – Launch Home Assistant in debug mode
#   ./scripts/ha.sh stop     – Stop Home Assistant
#   ./scripts/ha.sh restart  – Stop then start Home Assistant
# ---------------------------------------------------------------------------
set -euo pipefail
# set -x

# Resolve workspace root (parent of the directory containing this script)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_WORKSPACE="$(cd "${SCRIPT_DIR}/.." && pwd)"
WORKSPACE="${WORKSPACE:-${DEFAULT_WORKSPACE}}"
SCRIPTS_DIR="${WORKSPACE}/scripts"
CONFIG_DIR="${WORKSPACE}/config"

if [ ! -d "${WORKSPACE}" ]; then
    echo "[ha.sh] ERROR: WORKSPACE does not exist: ${WORKSPACE}" >&2
    exit 1
fi

if [ ! -f "${SCRIPTS_DIR}/setup.sh" ]; then
    echo "[ha.sh] ERROR: setup.sh not found at ${SCRIPTS_DIR}/setup.sh" >&2
    exit 1
fi

HA_PROCESS="${HA_PROCESS:-hass}"

ha_start() {
    echo "[ha.sh] Initializing environment …"
    # shellcheck source=setup.sh
    source "${SCRIPTS_DIR}/setup.sh"

    if ! command -v "${HA_PROCESS}" >/dev/null 2>&1; then
        echo "[ha.sh] ERROR: '${HA_PROCESS}' command not found in PATH." >&2
        exit 1
    fi

    echo "[ha.sh] Starting Home Assistant with config: ${CONFIG_DIR}"
    cd "${WORKSPACE}" || exit 1
    "${HA_PROCESS}" --config "${CONFIG_DIR}" --debug
}

ha_stop() {
    echo "[ha.sh] Stopping Home Assistant …"
    if pkill -f "${HA_PROCESS}"; then
        echo "[ha.sh] Home Assistant stopped."
    else
        echo "[ha.sh] No running Home Assistant process found."
    fi
}

ha_restart() {
    ha_stop
    # Give the process a moment to shut down cleanly
    sleep 2
    ha_start
}

case "${1:-}" in
    start)   ha_start   ;;
    stop)    ha_stop    ;;
    restart) ha_restart ;;
    *)
        echo "Usage: $0 {start|stop|restart}"
        exit 1
        ;;
esac

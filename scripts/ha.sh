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

# Resolve workspace root (parent of the directory containing this script)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE="${SCRIPT_DIR}/.."
CONFIG_DIR="${WORKSPACE}/config"

HA_PROCESS="hass"

ha_start() {
    echo "[ha.sh] Initializing environment …"
    # shellcheck source=setup.sh
    source "${SCRIPT_DIR}/setup.sh"

    echo "[ha.sh] Starting Home Assistant with config: ${CONFIG_DIR}"
    hass --config "${CONFIG_DIR}" --debug
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

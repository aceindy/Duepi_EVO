#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# smoke_migration.sh – Run Duepi EVO Home Assistant smoke tests in Docker.
#
# By default, this validates the migration path from the last stable pre-PR1
# release into the current checkout. The legacy phase can be skipped later
# without removing the normal smoke test.
# ---------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_WORKSPACE="$(cd "${SCRIPT_DIR}/.." && pwd)"
WORKSPACE="${WORKSPACE:-${DEFAULT_WORKSPACE}}"

FROM_REF="${DUEPI_MIGRATION_BASE_REF:-v2026.03.02}"
TO_REF=""
SKIP_MIGRATION=0

SMOKE_IMAGE="${DUEPI_SMOKE_IMAGE:-duepi-smoke-test:latest}"
NETWORK_NAME="duepi-smoke-net-$$"
EMULATOR_NAME="duepi-smoke-emulator-$$"
EMULATOR_HOST="duepi-smoke-emulator"
EMULATOR_PORT="${DUEPI_SMOKE_EMULATOR_PORT:-22345}"
STARTUP_TIMEOUT="${DUEPI_SMOKE_STARTUP_TIMEOUT:-45}"
CLIMATE_ENTITY_ID="${DUEPI_SMOKE_CLIMATE_ENTITY_ID:-climate.poele_pellets}"
LEGACY_UNIQUE_ID="${DUEPI_SMOKE_LEGACY_UNIQUE_ID:-poele_pellet}"
STABLE_BASE="${EMULATOR_HOST}:${EMULATOR_PORT}"

TMP_ROOT=""
FROM_WORKTREE=""
TO_WORKTREE=""
PHASE1_LOG=""
PHASE2_CHECK_LOG=""
PHASE2_START_LOG=""

usage() {
    cat <<EOF
Usage: $0 [--from-ref <git-ref>] [--to-ref <git-ref>] [--skip-migration]

Options:
  --from-ref <git-ref>   Legacy release to migrate from (default: ${FROM_REF})
  --to-ref <git-ref>     Target ref to validate instead of the current checkout
  --skip-migration       Skip the legacy phase and run only the current smoke test
EOF
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --from-ref)
            FROM_REF="${2:?missing value for --from-ref}"
            shift 2
            ;;
        --to-ref)
            TO_REF="${2:?missing value for --to-ref}"
            shift 2
            ;;
        --skip-migration)
            SKIP_MIGRATION=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "[smoke_migration] Unknown argument: $1" >&2
            usage >&2
            exit 1
            ;;
    esac
done

if [ ! -d "${WORKSPACE}" ]; then
    echo "[smoke_migration] ERROR: WORKSPACE does not exist: ${WORKSPACE}" >&2
    exit 1
fi

if [ ! -f "${WORKSPACE}/.devcontainer/Dockerfile" ]; then
    echo "[smoke_migration] ERROR: missing Dockerfile under ${WORKSPACE}/.devcontainer" >&2
    exit 1
fi

if [ ! -f "${WORKSPACE}/scripts/assert_ha_storage.py" ]; then
    echo "[smoke_migration] ERROR: missing helper script" >&2
    exit 1
fi

cleanup() {
    local exit_code=$?
    set +e
    if [ "${exit_code}" -ne 0 ]; then
        for logfile in "${PHASE1_LOG}" "${PHASE2_CHECK_LOG}" "${PHASE2_START_LOG}"; do
            if [ -n "${logfile}" ] && [ -f "${logfile}" ]; then
                echo ""
                echo "[smoke_migration] ---- ${logfile##*/} ----" >&2
                cat "${logfile}" >&2
            fi
        done
        docker logs "${EMULATOR_NAME}" 2>/dev/null >&2
    fi
    docker rm -f "${EMULATOR_NAME}" >/dev/null 2>&1
    docker network rm "${NETWORK_NAME}" >/dev/null 2>&1
    if [ -n "${FROM_WORKTREE}" ] && [ -d "${FROM_WORKTREE}" ]; then
        git -C "${WORKSPACE}" worktree remove --force "${FROM_WORKTREE}" >/dev/null 2>&1
    fi
    if [ -n "${TO_WORKTREE}" ] && [ -d "${TO_WORKTREE}" ]; then
        git -C "${WORKSPACE}" worktree remove --force "${TO_WORKTREE}" >/dev/null 2>&1
    fi
    if [ -n "${TMP_ROOT}" ] && [ -d "${TMP_ROOT}" ]; then
        rm -rf "${TMP_ROOT}"
    fi
    exit "${exit_code}"
}
trap cleanup EXIT

create_worktree() {
    local ref="$1"
    local target_dir="$2"
    git -C "${WORKSPACE}" rev-parse --verify "${ref}^{commit}" >/dev/null
    git -C "${WORKSPACE}" worktree add --detach "${target_dir}" "${ref}" >/dev/null
}

build_image() {
    echo "[smoke_migration] Building Docker image ${SMOKE_IMAGE}"
    docker build -t "${SMOKE_IMAGE}" -f "${WORKSPACE}/.devcontainer/Dockerfile" "${WORKSPACE}" >/dev/null
}

start_emulator() {
    echo "[smoke_migration] Starting emulator ${EMULATOR_NAME}"
    docker network create "${NETWORK_NAME}" >/dev/null
    docker run -d --rm \
        --name "${EMULATOR_NAME}" \
        --network "${NETWORK_NAME}" \
        --network-alias "${EMULATOR_HOST}" \
        -v "${WORKSPACE}:/workspace:ro" \
        "${SMOKE_IMAGE}" \
        python3 /workspace/evo-python/EVO-sim.py \
            --host 0.0.0.0 \
            --port "${EMULATOR_PORT}" \
            --ui-port 18080 >/dev/null
}

wait_for_emulator() {
    local attempt
    for attempt in $(seq 1 20); do
        if docker run --rm --network "${NETWORK_NAME}" "${SMOKE_IMAGE}" python3 - <<PY >/dev/null 2>&1
import socket
sock = socket.create_connection(("${EMULATOR_HOST}", ${EMULATOR_PORT}), timeout=1)
sock.close()
PY
        then
            echo "[smoke_migration] Emulator is reachable"
            return
        fi
        sleep 1
    done

    echo "[smoke_migration] ERROR: emulator did not become reachable" >&2
    return 1
}

write_config() {
    local config_dir="$1"
    mkdir -p "${config_dir}" "${config_dir}/custom_components" "${config_dir}/.storage"
    cat > "${config_dir}/configuration.yaml" <<EOF
frontend:
config:
history:
logbook:
homeassistant:
system_health:
energy:

logger:
  default: warning
  logs:
    custom_components.duepi_evo: debug

recorder:
  auto_purge: true
  purge_keep_days: 1
  commit_interval: 1
  include:
    domains:
      - climate
      - sensor
      - binary_sensor

climate:
  - platform: duepi_evo
    name: Poele Pellets
    host: ${EMULATOR_HOST}
    port: ${EMULATOR_PORT}
    scan_interval: 5
    min_temp: 20
    max_temp: 30
    auto_reset: true
    unique_id: ${LEGACY_UNIQUE_ID}
    temp_nofeedback: 16
    init_command: false
EOF
}

install_component() {
    local source_root="$1"
    local config_dir="$2"
    rm -rf "${config_dir}/custom_components/duepi_evo"
    cp -R "${source_root}/custom_components/duepi_evo" "${config_dir}/custom_components/duepi_evo"
}

assert_logs_clean() {
    local logfile="$1"
    if grep -En "Traceback \\(most recent call last\\)|Error while setting up duepi_evo|Platform error climate\\.duepi_evo|Setup failed for custom integration duepi_evo" "${logfile}" >/dev/null; then
        echo "[smoke_migration] ERROR: blocking error detected in ${logfile}" >&2
        return 1
    fi
}

run_check_config() {
    local config_dir="$1"
    local logfile="$2"
    echo "[smoke_migration] Running hass --script check_config"
    docker run --rm \
        --name "duepi-smoke-check-$$" \
        --network "${NETWORK_NAME}" \
        -v "${config_dir}:/config" \
        "${SMOKE_IMAGE}" \
        bash -lc "hass --script check_config --config /config" >"${logfile}" 2>&1
}

run_hass_startup() {
    local config_dir="$1"
    local logfile="$2"
    echo "[smoke_migration] Starting Home Assistant for ${STARTUP_TIMEOUT}s"
    local status=0
    set +e
    docker run --rm \
        --name "duepi-smoke-ha-$$" \
        --network "${NETWORK_NAME}" \
        -v "${config_dir}:/config" \
        "${SMOKE_IMAGE}" \
        bash -lc "timeout ${STARTUP_TIMEOUT}s hass --config /config --debug" >"${logfile}" 2>&1
    status=$?
    set -e

    if [ "${status}" -ne 0 ] && [ "${status}" -ne 124 ]; then
        echo "[smoke_migration] ERROR: Home Assistant exited with status ${status}" >&2
        return "${status}"
    fi

    assert_logs_clean "${logfile}"
}

prepare_target_root() {
    if [ -n "${TO_REF}" ]; then
        TO_WORKTREE="${TMP_ROOT}/to-worktree"
        create_worktree "${TO_REF}" "${TO_WORKTREE}"
        printf '%s\n' "${TO_WORKTREE}"
        return
    fi
    printf '%s\n' "${WORKSPACE}"
}

TMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/duepi-smoke.XXXXXX")"
CONFIG_DIR="${TMP_ROOT}/config"
PHASE1_LOG="${TMP_ROOT}/phase1-ha.log"
PHASE2_CHECK_LOG="${TMP_ROOT}/phase2-check.log"
PHASE2_START_LOG="${TMP_ROOT}/phase2-ha.log"

write_config "${CONFIG_DIR}"
build_image
start_emulator
wait_for_emulator

TARGET_ROOT="$(prepare_target_root)"

if [ "${SKIP_MIGRATION}" -eq 0 ]; then
    FROM_WORKTREE="${TMP_ROOT}/from-worktree"
    create_worktree "${FROM_REF}" "${FROM_WORKTREE}"

    echo "[smoke_migration] Phase 1: legacy startup from ${FROM_REF}"
    install_component "${FROM_WORKTREE}" "${CONFIG_DIR}"
    run_hass_startup "${CONFIG_DIR}" "${PHASE1_LOG}"
    python3 "${WORKSPACE}/scripts/assert_ha_storage.py" \
        phase1 \
        "${CONFIG_DIR}" \
        --climate-entity-id "${CLIMATE_ENTITY_ID}" \
        --legacy-unique-id "${LEGACY_UNIQUE_ID}"
fi

echo "[smoke_migration] Phase 2: upgrade/startup using ${TO_REF:-current checkout}"
install_component "${TARGET_ROOT}" "${CONFIG_DIR}"
run_check_config "${CONFIG_DIR}" "${PHASE2_CHECK_LOG}"
run_hass_startup "${CONFIG_DIR}" "${PHASE2_START_LOG}"
python3 "${WORKSPACE}/scripts/assert_ha_storage.py" \
    phase2 \
    "${CONFIG_DIR}" \
    --climate-entity-id "${CLIMATE_ENTITY_ID}" \
    --stable-base "${STABLE_BASE}"

echo "[smoke_migration] SUCCESS"
if [ "${SKIP_MIGRATION}" -eq 1 ]; then
    echo "[smoke_migration] Verified current smoke test without legacy migration"
else
    echo "[smoke_migration] Verified legacy migration from ${FROM_REF} into ${TO_REF:-current checkout}"
fi

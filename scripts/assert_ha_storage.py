#!/usr/bin/env python3
"""Assert Duepi EVO Home Assistant storage state during smoke tests."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

DOMAIN = "duepi_evo"

EXPECTED_SENSOR_KEYS = (
    "burner_status",
    "error_code",
    "exh_fan_speed",
    "flu_gas_temp",
    "pellet_speed",
    "power_level",
    "pcb_temp",
    "total_burn_time",
    "burn_time_since_reset",
)
EXPECTED_BINARY_SENSOR_KEYS = ("pressure_switch",)


def _fail(message: str) -> None:
    print(f"[assert_ha_storage] ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def _load_storage(config_dir: Path, storage_name: str) -> dict[str, Any]:
    path = config_dir / ".storage" / storage_name
    if not path.exists():
        _fail(f"Missing storage file: {path}")

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as err:
        _fail(f"Invalid JSON in {path}: {err}")

    data = payload.get("data")
    if not isinstance(data, dict):
        _fail(f"Unexpected storage payload in {path}")
    return data


def _entity_entries(config_dir: Path) -> list[dict[str, Any]]:
    data = _load_storage(config_dir, "core.entity_registry")
    entities = data.get("entities")
    if not isinstance(entities, list):
        _fail("core.entity_registry does not contain a list of entities")
    return entities


def _config_entries(config_dir: Path) -> list[dict[str, Any]]:
    path = config_dir / ".storage" / "core.config_entries"
    if not path.exists():
        return []

    data = _load_storage(config_dir, "core.config_entries")
    entries = data.get("entries")
    if not isinstance(entries, list):
        _fail("core.config_entries does not contain a list of entries")
    return entries


def _duepi_entities(config_dir: Path) -> list[dict[str, Any]]:
    return [entry for entry in _entity_entries(config_dir) if entry.get("platform") == DOMAIN]


def _duepi_config_entries(config_dir: Path) -> list[dict[str, Any]]:
    return [entry for entry in _config_entries(config_dir) if entry.get("domain") == DOMAIN]


def _entity_domain(entry: dict[str, Any]) -> str | None:
    entity_id = entry.get("entity_id")
    if not isinstance(entity_id, str) or "." not in entity_id:
        return None
    return entity_id.split(".", 1)[0]


def _one(entries: list[dict[str, Any]], *, label: str) -> dict[str, Any]:
    if len(entries) != 1:
        _fail(f"Expected exactly one {label}, found {len(entries)}")
    return entries[0]


def assert_phase1(config_dir: Path, climate_entity_id: str, legacy_unique_id: str) -> None:
    duepi_config_entries = _duepi_config_entries(config_dir)
    if duepi_config_entries:
        _fail("Legacy phase should not have created a duepi_evo config entry yet")

    climate_entries = [
        entry
        for entry in _duepi_entities(config_dir)
        if _entity_domain(entry) == "climate" and entry.get("entity_id") == climate_entity_id
    ]
    climate_entry = _one(climate_entries, label="legacy climate entity")

    if climate_entry.get("unique_id") != legacy_unique_id:
        _fail(
            f"Legacy climate unique_id mismatch: expected {legacy_unique_id}, "
            f"got {climate_entry.get('unique_id')}"
        )

    if climate_entry.get("config_entry_id"):
        _fail("Legacy climate entity should not be linked to a config entry yet")

    print(
        "[assert_ha_storage] Phase 1 OK:",
        climate_entry.get("entity_id"),
        climate_entry.get("unique_id"),
    )


def assert_phase2(config_dir: Path, climate_entity_id: str, stable_base: str) -> None:
    duepi_config_entry = _one(_duepi_config_entries(config_dir), label="duepi_evo config entry")

    if duepi_config_entry.get("unique_id") != stable_base:
        _fail(
            f"Config-entry unique_id mismatch: expected {stable_base}, "
            f"got {duepi_config_entry.get('unique_id')}"
        )

    if duepi_config_entry.get("source") != "import":
        _fail(
            f"Config-entry source mismatch: expected import, got {duepi_config_entry.get('source')}"
        )

    duepi_entities = _duepi_entities(config_dir)
    climate_entries = [entry for entry in duepi_entities if _entity_domain(entry) == "climate"]
    climate_entry = _one(climate_entries, label="migrated climate entity")

    if climate_entry.get("entity_id") != climate_entity_id:
        _fail(
            f"Climate entity_id mismatch: expected {climate_entity_id}, "
            f"got {climate_entry.get('entity_id')}"
        )

    expected_climate_unique_id = f"{stable_base}:climate"
    if climate_entry.get("unique_id") != expected_climate_unique_id:
        _fail(
            f"Climate unique_id mismatch: expected {expected_climate_unique_id}, "
            f"got {climate_entry.get('unique_id')}"
        )

    if climate_entry.get("config_entry_id") != duepi_config_entry.get("entry_id"):
        _fail("Climate entity is not linked to the imported config entry")

    sensor_unique_ids = {
        entry.get("unique_id")
        for entry in duepi_entities
        if _entity_domain(entry) == "sensor"
    }
    binary_sensor_unique_ids = {
        entry.get("unique_id")
        for entry in duepi_entities
        if _entity_domain(entry) == "binary_sensor"
    }

    expected_sensor_unique_ids = {
        f"{stable_base}:sensor:{key}" for key in EXPECTED_SENSOR_KEYS
    }
    expected_binary_sensor_unique_ids = {
        f"{stable_base}:binary_sensor:{key}" for key in EXPECTED_BINARY_SENSOR_KEYS
    }

    missing_sensors = sorted(expected_sensor_unique_ids - sensor_unique_ids)
    if missing_sensors:
        _fail(f"Missing expected sensors: {', '.join(missing_sensors)}")

    missing_binary_sensors = sorted(
        expected_binary_sensor_unique_ids - binary_sensor_unique_ids
    )
    if missing_binary_sensors:
        _fail(
            "Missing expected binary sensors: "
            + ", ".join(missing_binary_sensors)
        )

    print(
        "[assert_ha_storage] Phase 2 OK:",
        climate_entry.get("entity_id"),
        climate_entry.get("unique_id"),
        f"{len(sensor_unique_ids)} sensors",
        f"{len(binary_sensor_unique_ids)} binary sensors",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("phase1", "phase2"))
    parser.add_argument("config_dir", type=Path)
    parser.add_argument("--climate-entity-id", default="climate.poele_pellets")
    parser.add_argument("--legacy-unique-id", default="poele_pellet")
    parser.add_argument("--stable-base")
    args = parser.parse_args()

    config_dir = args.config_dir.resolve()
    if not config_dir.exists():
        _fail(f"Config directory does not exist: {config_dir}")

    if args.phase == "phase1":
        assert_phase1(config_dir, args.climate_entity_id, args.legacy_unique_id)
        return

    if not args.stable_base:
        _fail("--stable-base is required for phase2")
    assert_phase2(config_dir, args.climate_entity_id, args.stable_base)


if __name__ == "__main__":
    main()

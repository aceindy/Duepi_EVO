"""Entity-registry migration tests for Duepi EVO."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from types import SimpleNamespace

from homeassistant.const import CONF_HOST, CONF_PORT

from custom_components.duepi_evo.const import CONF_UNIQUE_ID, DEFAULT_UNIQUE_ID, DOMAIN
from custom_components.duepi_evo.entity_migration import (
    legacy_climate_entity_unique_ids,
    migrate_climate_entity_registry,
    stable_climate_entity_unique_id,
    stable_yaml_fallback_unique_id,
)


@dataclass
class FakeRegistryEntry:
    """Minimal entity-registry entry used by migration tests."""

    entity_id: str
    unique_id: str
    domain: str = "climate"
    platform: str = DOMAIN
    config_entry_id: str | None = None


class FakeEntityRegistry:
    """Small in-memory entity registry."""

    def __init__(self, *entries: FakeRegistryEntry) -> None:
        self.entities: dict[str, FakeRegistryEntry] = {
            entry.entity_id: entry for entry in entries
        }

    def async_get_entity_id(self, domain: str, platform: str, unique_id: str) -> str | None:
        """Return the current entity ID for a domain/platform/unique_id tuple."""
        for entry in self.entities.values():
            if (
                entry.domain == domain
                and entry.platform == platform
                and entry.unique_id == unique_id
            ):
                return entry.entity_id
        return None

    def async_update_entity(
        self,
        entity_id: str,
        *,
        new_unique_id: str | None = None,
        config_entry_id: str | None = None,
    ) -> FakeRegistryEntry:
        """Update a fake entity-registry entry."""
        entry = self.entities[entity_id]
        if new_unique_id is not None:
            entry.unique_id = new_unique_id
        if config_entry_id is not None:
            entry.config_entry_id = config_entry_id
        return entry

    def async_remove(self, entity_id: str) -> None:
        """Remove a fake entity-registry entry."""
        self.entities.pop(entity_id, None)


def _entry(
    *,
    entry_id: str,
    host: str = "192.168.1.12",
    port: int = 2000,
    config_entry_unique_id: str | None = None,
    configured_unique_id: str = DEFAULT_UNIQUE_ID,
):
    """Build a minimal config-entry-like object for migration helpers."""
    return SimpleNamespace(
        entry_id=entry_id,
        unique_id=config_entry_unique_id or f"{host}:{port}",
        data={
            CONF_HOST: host,
            CONF_PORT: port,
            CONF_UNIQUE_ID: configured_unique_id,
        },
    )


def test_stable_climate_unique_id_is_independent_of_entry_id() -> None:
    """Stable climate unique IDs should not depend on the config entry ID."""
    first = _entry(entry_id="entry-a")
    second = _entry(entry_id="entry-b")

    assert stable_climate_entity_unique_id(first) == "192.168.1.12:2000:climate"
    assert stable_climate_entity_unique_id(second) == "192.168.1.12:2000:climate"
    assert stable_yaml_fallback_unique_id("192.168.1.12", 2000) == "192.168.1.12:2000:climate"


def test_legacy_climate_unique_ids_cover_known_formats() -> None:
    """Known legacy climate unique-ID formats should be enumerated for migration."""
    entry = _entry(entry_id="entry-a")

    assert legacy_climate_entity_unique_ids(entry) == (
        DEFAULT_UNIQUE_ID,
        "yaml_duepi_unique_192.168.1.12_2000",
        "192.168.1.12:2000:climate",
    )


def test_migration_prefers_original_legacy_entity_and_removes_duplicates() -> None:
    """Migration should keep the oldest legacy entity and remove the duplicate ones."""
    entry = _entry(entry_id="entry-new")
    registry = FakeEntityRegistry(
        FakeRegistryEntry("climate.poele_pellets", DEFAULT_UNIQUE_ID),
        FakeRegistryEntry(
            "climate.poele_pellets_yaml",
            "yaml_duepi_unique_192.168.1.12_2000",
        ),
        FakeRegistryEntry(
            "climate.poele_pellets_entry",
            "old-entry_duepi_unique",
        ),
    )

    assert migrate_climate_entity_registry(registry, entry) is True
    assert list(registry.entities) == ["climate.poele_pellets"]
    assert registry.entities["climate.poele_pellets"].unique_id == "192.168.1.12:2000:climate"
    assert registry.entities["climate.poele_pellets"].config_entry_id == "entry-new"


def test_migration_handles_recreated_entries_from_old_pr1_format() -> None:
    """Recreated config entries should adopt the old entity instead of creating a duplicate."""
    entry = _entry(entry_id="entry-new")
    registry = FakeEntityRegistry(
        FakeRegistryEntry(
            "climate.poele_pellets",
            "entry-old_duepi_unique",
            config_entry_id="entry-old",
        )
    )

    assert migrate_climate_entity_registry(registry, entry) is True
    assert list(registry.entities) == ["climate.poele_pellets"]
    assert registry.entities["climate.poele_pellets"].unique_id == "192.168.1.12:2000:climate"
    assert registry.entities["climate.poele_pellets"].config_entry_id == "entry-new"


def test_translation_files_exist_and_parse() -> None:
    """Runtime translation files should exist for the main tested locales."""
    repo_root = Path(__file__).resolve().parents[1]
    translations_dir = repo_root / "custom_components" / "duepi_evo" / "translations"

    for locale in ("en", "fr"):
        path = translations_dir / f"{locale}.json"
        assert path.exists()
        with path.open(encoding="utf-8") as file_obj:
            payload = json.load(file_obj)
        assert "config" in payload
        assert "options" in payload

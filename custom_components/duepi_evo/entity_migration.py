"""Helpers for stable climate entity IDs and registry migration."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from homeassistant.const import CONF_HOST, CONF_PORT

from .const import (
    CONF_UNIQUE_ID,
    DEFAULT_UNIQUE_ID,
    DOMAIN,
    climate_unique_id,
    climate_unique_id_from_entry_unique_id,
    entry_unique_id,
)

CLIMATE_DOMAIN = "climate"


def stable_climate_entity_unique_id(entry: Any) -> str:
    """Return the stable climate unique ID for a config entry."""
    return climate_unique_id_from_entry_unique_id(
        getattr(entry, "unique_id", None)
        or entry_unique_id(entry.data[CONF_HOST], entry.data[CONF_PORT])
    )


def legacy_climate_entity_unique_ids(entry: Any) -> tuple[str, ...]:
    """Return legacy climate unique IDs that may already exist in the registry."""
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    configured_unique_id = entry.data.get(CONF_UNIQUE_ID, DEFAULT_UNIQUE_ID)
    unique_ids = [
        configured_unique_id,
        f"yaml_{configured_unique_id}_{host}_{port}",
        stable_climate_entity_unique_id(entry),
    ]

    # Preserve order while removing duplicates.
    return tuple(dict.fromkeys(unique_ids))


def _iter_existing_entity_ids(
    registry: Any, unique_ids: Iterable[str]
) -> dict[str, str]:
    """Resolve candidate unique IDs to current entity IDs."""
    existing: dict[str, str] = {}
    for unique_id in unique_ids:
        entity_id = registry.async_get_entity_id(CLIMATE_DOMAIN, DOMAIN, unique_id)
        if entity_id:
            existing[unique_id] = entity_id
    return existing


def _iter_legacy_entry_scoped_unique_ids(
    registry: Any, configured_unique_id: str
) -> tuple[str, ...]:
    """Return old PR1 entry-scoped climate unique IDs still present in the registry."""
    entities = getattr(registry, "entities", {})
    values = entities.values() if hasattr(entities, "values") else ()
    suffix = f"_{configured_unique_id}"
    legacy_unique_ids: list[str] = []

    for entity in values:
        if getattr(entity, "domain", None) != CLIMATE_DOMAIN:
            continue
        if getattr(entity, "platform", None) != DOMAIN:
            continue

        unique_id = getattr(entity, "unique_id", "")
        if (
            unique_id.endswith(suffix)
            and unique_id != configured_unique_id
            and not unique_id.startswith("yaml_")
            and not unique_id.endswith(":climate")
        ):
            legacy_unique_ids.append(unique_id)

    return tuple(dict.fromkeys(legacy_unique_ids))


def migrate_climate_entity_registry(registry: Any, entry: Any) -> bool:
    """Migrate known legacy climate unique IDs to the stable current format."""

    if entry.version and entry.version >= 1:
        return False

    target_unique_id = stable_climate_entity_unique_id(entry)
    configured_unique_id = entry.data.get(CONF_UNIQUE_ID, DEFAULT_UNIQUE_ID)
    candidates = (
        *legacy_climate_entity_unique_ids(entry),
        *_iter_legacy_entry_scoped_unique_ids(registry, configured_unique_id),
    )
    candidates = tuple(dict.fromkeys(candidates))
    existing = _iter_existing_entity_ids(registry, candidates)
    if not existing:
        return False

    preferred_order = candidates
    canonical_unique_id = next(
        unique_id for unique_id in preferred_order if unique_id in existing
    )
    canonical_entity_id = existing[canonical_unique_id]
    removed_entity_ids: set[str] = set()

    target_entity_id = existing.get(target_unique_id)
    if target_entity_id and target_entity_id != canonical_entity_id:
        registry.async_remove(target_entity_id)
        removed_entity_ids.add(target_entity_id)

    registry.async_update_entity(
        canonical_entity_id,
        new_unique_id=target_unique_id,
        config_entry_id=entry.entry_id,
    )

    for unique_id in candidates:
        entity_id = existing.get(unique_id)
        if (
            not entity_id
            or entity_id == canonical_entity_id
            or entity_id in removed_entity_ids
        ):
            continue
        registry.async_remove(entity_id)
        removed_entity_ids.add(entity_id)

    return True


def stable_yaml_fallback_unique_id(host: str, port: int) -> str:
    """Return the stable climate unique ID used by YAML fallback entities."""
    return climate_unique_id(host, port)

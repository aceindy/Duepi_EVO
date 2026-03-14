"""Shared device metadata helpers for Duepi EVO entities."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN

DEVICE_MANUFACTURER = "Duepi EVO"
DEVICE_MODEL = "Pellet Stove"


def build_device_info(unique_base: str, name: str) -> DeviceInfo:
    """Return device metadata shared by all Duepi EVO entities for one stove."""
    return DeviceInfo(
        identifiers={(DOMAIN, unique_base)},
        name=name,
        manufacturer=DEVICE_MANUFACTURER,
        model=DEVICE_MODEL,
    )

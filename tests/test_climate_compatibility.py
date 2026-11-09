"""Check climate API compatibility without installing Home Assistant."""

from __future__ import annotations

import ast
from enum import IntFlag
from pathlib import Path
from types import SimpleNamespace
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "custom_components/duepi_evo/climate.py"


def climate_class(native_api: bool, turn_features: bool):
    """Load the actual entity class against either generation of the climate API."""
    tree = ast.parse(SOURCE.read_text())
    tree.body = [
        node for node in tree.body
        if isinstance(node, ast.ClassDef)
        or (
            isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "SUPPORT_FLAGS"
                    for target in node.targets)
        )
    ]

    class ClimateEntity:
        pass

    if native_api:
        ClimateEntity.native_temperature_unit = property(
            lambda self: self._attr_native_temperature_unit
        )
        ClimateEntity.native_current_temperature = property(lambda self: None)
        ClimateEntity.native_target_temperature = property(lambda self: None)

    class CoordinatorEntity:
        def __class_getitem__(cls, item):
            return cls

    features = {"TARGET_TEMPERATURE": 1, "FAN_MODE": 2}
    if turn_features:
        features.update(TURN_ON=4, TURN_OFF=8)
    namespace = {
        "__name__": __name__,
        "ClimateEntity": ClimateEntity,
        "CoordinatorEntity": CoordinatorEntity,
        "DuepiEvoCoordinator": object,
        "ClimateEntityFeature": IntFlag("ClimateEntityFeature", features),
        "UnitOfTemperature": SimpleNamespace(CELSIUS="°C"),
    }
    exec(compile(tree, str(SOURCE), "exec"), namespace)
    return namespace["DuepiEvoClimateEntity"]


class ClimateCompatibilityTests(unittest.TestCase):
    def test_temperature_apis(self):
        for native_api, turn_features in ((False, False), (False, True), (True, True)):
            with self.subTest(native_api=native_api, turn_features=turn_features):
                cls = climate_class(native_api, turn_features)
                entity = cls.__new__(cls)
                entity.coordinator = SimpleNamespace(data=SimpleNamespace(
                    current_temp_c=21.5, target_temp_c=24.0
                ))
                entity._last_target_temperature = None
                entity._no_feedback = 16.0
                prefix = "native_" if native_api else ""
                self.assertEqual(getattr(entity, prefix + "current_temperature"), 21.5)
                self.assertEqual(getattr(entity, prefix + "target_temperature"), 24.0)
                unit_attr = "_attr_" + prefix + "temperature_unit"
                self.assertEqual(getattr(entity, unit_attr), "°C")
                entity.coordinator.data = None
                self.assertIsNone(getattr(entity, prefix + "current_temperature"))
                self.assertEqual(getattr(entity, prefix + "target_temperature"), 16.0)
                entity._last_target_temperature = 25.0
                self.assertEqual(getattr(entity, prefix + "target_temperature"), 25.0)
                self.assertEqual(int(entity._attr_supported_features), 15 if turn_features else 3)
                if native_api:
                    self.assertNotIn("current_temperature", cls.__dict__)
                    self.assertNotIn("target_temperature", cls.__dict__)
                    self.assertNotIn("_attr_temperature_unit", cls.__dict__)

    def test_temperature_unit_import_uses_public_constants(self):
        imports = {
            node.module: {alias.name for alias in node.names}
            for node in ast.walk(ast.parse(SOURCE.read_text()))
            if isinstance(node, ast.ImportFrom)
        }
        self.assertIn("UnitOfTemperature", imports["homeassistant.const"])
        self.assertNotIn("UnitOfTemperature", imports["homeassistant.components.climate"])
        self.assertNotIn("REVOLUTIONS_PER_MINUTE", imports["homeassistant.const"])


if __name__ == "__main__":
    unittest.main()

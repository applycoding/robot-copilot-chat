from __future__ import annotations

import pytest

from robot_copilot.vehicles import VehicleConfigError, load_vehicles
from tests.helpers import ROOT


def test_demo_vehicles_load():
    load_vehicles(ROOT / "config/vehicles.toml")


def test_cruise_exceeds_max(tmp_path):
    raw = (ROOT / "config/vehicles.toml").read_text()
    bad = raw.replace("max_speed_mps = 15.0", "max_speed_mps = 5.0", 1)
    p = tmp_path / "v.toml"
    p.write_text(bad)
    with pytest.raises(VehicleConfigError):
        load_vehicles(p)


def test_altitude_order(tmp_path):
    raw = (ROOT / "config/vehicles.toml").read_text()
    bad = raw.replace("default_altitude_m = 30.0", "default_altitude_m = 200.0", 1)
    p = tmp_path / "v.toml"
    p.write_text(bad)
    with pytest.raises(VehicleConfigError):
        load_vehicles(p)

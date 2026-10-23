from __future__ import annotations

import pytest

from robot_copilot.settings import load_settings
from robot_copilot.site import (
    SiteConfigError,
    load_site,
    normalize_name,
    resolve_place,
    suggest_places,
)
from tests.helpers import default_settings_env


def test_demo_site_loads():
    s = load_settings(env=default_settings_env(), dotenv_enabled=False)
    site = load_site(s.site_path)
    assert site.name
    assert len(site.places) >= 5


def test_normalize_and_resolve():
    s = load_settings(env=default_settings_env(), dotenv_enabled=False)
    site = load_site(s.site_path)
    assert normalize_name("the BARN.") == normalize_name("barn")
    assert resolve_place(site, "barn") is not None
    assert resolve_place(site, "neighbor's house") is None
    assert suggest_places(site, "barnn")


def test_invalid_geofence(tmp_path):
    p = tmp_path / "bad.toml"
    p.write_text("""
[site]
id = "x"
name = "x"
home = [0, 0]
geofence = [[0,0],[1,0]]
geofence_margin_m = 5.0
[[places]]
name = "P"
kind = "point"
points = [[0,0]]
""")
    with pytest.raises((SiteConfigError, Exception)):
        load_site(p)

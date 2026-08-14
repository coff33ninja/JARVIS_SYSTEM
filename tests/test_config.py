"""Config defaults, YAML round-trip, and invalid-value tolerance."""

from __future__ import annotations

import yaml

from app.config import AppConfig, ControlConfig, PerceptionConfig


def test_defaults_are_sane():
    cfg = AppConfig.defaults()
    assert cfg.perception.camera_index == 0
    assert cfg.perception.width == 640
    assert cfg.control.min_cutoff == 1.0
    assert cfg.control.beta == 0.007
    assert cfg.control.failsafe is False
    assert cfg.hud.port == 8765


def test_missing_file_gives_defaults(tmp_path):
    cfg = AppConfig.load(tmp_path / "nope.yaml")
    assert cfg == AppConfig.defaults()


def test_load_none_uses_default_config_path(tmp_path, monkeypatch):
    from app import config as config_mod

    monkeypatch.setattr(config_mod, "CONFIG_FILE", tmp_path / "absent.yaml")
    assert AppConfig.load(None) == AppConfig.defaults()


def test_save_load_roundtrip(tmp_path):
    path = tmp_path / "jarvis.yaml"
    cfg = AppConfig.defaults()
    cfg.perception.camera_index = 2
    cfg.control.gain_x = 5.5
    cfg.control.invert_x = False
    cfg.hud.port = 9999
    cfg.save(path)
    loaded = AppConfig.load(path)
    assert loaded.perception.camera_index == 2
    assert loaded.control.gain_x == 5.5
    assert loaded.control.invert_x is False
    assert loaded.hud.port == 9999


def test_load_coerces_strings(tmp_path):
    path = tmp_path / "j.yaml"
    path.write_text(yaml.safe_dump({"control": {"gain_x": "4.2", "invert_x": "true"}}))
    cfg = AppConfig.load(path)
    assert cfg.control.gain_x == 4.2
    assert cfg.control.invert_x is True


def test_invalid_value_falls_back_to_default(tmp_path):
    path = tmp_path / "j.yaml"
    path.write_text(yaml.safe_dump({"control": {"gain_x": "not-a-number"}}))
    cfg = AppConfig.load(path)
    assert cfg.control.gain_x == ControlConfig().gain_x


def test_invalid_section_ignored(tmp_path):
    path = tmp_path / "j.yaml"
    path.write_text(yaml.safe_dump({"bogus_section": {"a": 1}}))
    cfg = AppConfig.load(path)
    assert cfg == AppConfig.defaults()


def test_corrupt_yaml_gives_defaults(tmp_path):
    path = tmp_path / "j.yaml"
    path.write_text("control: [unclosed\n  - {bad")
    cfg = AppConfig.load(path)
    assert cfg == AppConfig.defaults()


def test_partial_config_keeps_other_defaults(tmp_path):
    path = tmp_path / "j.yaml"
    path.write_text(yaml.safe_dump({"perception": {"camera_index": 3}}))
    cfg = AppConfig.load(path)
    assert cfg.perception.camera_index == 3
    assert cfg.perception.width == PerceptionConfig().width


def test_save_creates_parent_dir(tmp_path):
    path = tmp_path / "a" / "b" / "jarvis.yaml"
    AppConfig.defaults().save(path)
    assert path.exists()


def test_to_dict_matches_dataclass_fields():
    cfg = AppConfig.defaults()
    d = cfg.to_dict()
    assert set(d) == {"perception", "control", "hud"}
    assert set(d["control"]) >= {"gain_x", "invert_x", "pinch_threshold"}

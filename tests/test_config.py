"""Unit tests for haul.config — HAUL must work with zero
configuration, and CLI flags always override the file (spec §26)."""

from __future__ import annotations

from haul.config import Config, load_config


def test_missing_config_file_returns_defaults(tmp_path):
    config = load_config(tmp_path / "does-not-exist.toml")
    assert config == Config()


def test_loads_values_from_toml(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('output = "~/Downloads/haul"\nquality = "1080p"\nmetadata = true\n')
    config = load_config(path)
    assert config.output == "~/Downloads/haul"
    assert config.quality == "1080p"
    assert config.metadata is True


def test_unknown_keys_are_ignored(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('made_up_field = "surprise"\nquality = "720p"\n')
    config = load_config(path)
    assert config.quality == "720p"
    assert not hasattr(config, "made_up_field")


def test_partial_config_keeps_other_defaults(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('quality = "480p"\n')
    config = load_config(path)
    assert config.quality == "480p"
    assert config.output == Config().output
    assert config.concurrency == Config().concurrency

"""Optional configuration file (spec §26): ``~/.config/haul/config.toml``.

HAUL works with zero configuration — every field here has a sensible
default, and CLI flags always take precedence over the config file.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, fields
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - only exercised on Python < 3.11
    import tomli as tomllib

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "haul" / "config.toml"


@dataclass
class Config:
    output: str = "downloads"
    quality: str = "best"
    metadata: bool = False
    concurrency: int = 3


def load_config(path: Path | None = None) -> Config:
    """Reads the config file if it exists; otherwise returns
    defaults. Unknown keys are ignored rather than raising, so an
    older/newer config file never breaks the tool."""
    path = path or DEFAULT_CONFIG_PATH
    config = Config()
    if not path.exists():
        return config

    with open(path, "rb") as f:
        data = tomllib.load(f)

    known_fields = {f.name for f in fields(Config)}
    for key, value in data.items():
        if key in known_fields:
            setattr(config, key, value)
    return config

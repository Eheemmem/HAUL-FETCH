"""Writes the optional JSON metadata sidecar file (spec §15).

    video.mp4
    video.json
"""

from __future__ import annotations

import json
from pathlib import Path

from .extractor import MediaFormat, MediaInfo


def write_metadata(info: MediaInfo, chosen: MediaFormat, media_path: Path) -> Path:
    metadata_path = media_path.with_suffix(".json")
    data = info.to_metadata_dict(chosen)
    data["original_filename"] = media_path.name
    metadata_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return metadata_path

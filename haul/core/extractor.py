"""The normalized media model (spec §22) and the extractor interface
(spec §21) every platform implements.

This is the seam that keeps the rest of HAUL platform-independent:
extractors *discover* media and describe it as MediaInfo/MediaFormat
objects. They never touch the network for content and never touch
the filesystem — that's the Downloader's job. Adding a platform means
writing something that fills in this model; nothing else changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class MediaType(str, Enum):
    VIDEO = "video"
    IMAGE = "image"
    GALLERY = "gallery"
    AUDIO = "audio"
    PROFILE_PICTURE = "profile_picture"


@dataclass
class MediaFormat:
    """One concrete, already-existing representation of a piece of
    media — one quality tier, one file. The selector picks among
    these; it never invents or upscales one (spec §11)."""

    url: str | None
    extension: str
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    bitrate: float | None = None
    codec: str | None = None
    filesize: int | None = None
    has_audio: bool = True
    format_note: str | None = None

    # Set when video and audio are delivered as separate streams
    # (common for DASH-style delivery on YouTube). The downloader
    # fetches both and hands them to FFmpeg to mux (spec §10).
    audio_url: str | None = None
    audio_extension: str | None = None

    @property
    def quality_label(self) -> str:
        if self.height:
            fps_part = f"{int(self.fps)}fps" if self.fps and self.fps > 30 else ""
            return " ".join(p for p in (f"{self.height}p", fps_part) if p)
        return self.format_note or "original"

    @property
    def resolution_label(self) -> str:
        if self.width and self.height:
            return f"{self.width}x{self.height}"
        return "unknown"


@dataclass
class MediaInfo:
    """Normalized description of one downloadable item, produced by
    an extractor and consumed by the selector and downloader."""

    platform: str
    media_type: MediaType
    id: str
    source_url: str
    author: str | None = None
    title: str | None = None
    upload_date: str | None = None
    duration: float | None = None
    thumbnail: str | None = None
    formats: list[MediaFormat] = field(default_factory=list)
    audio_formats: list[MediaFormat] = field(default_factory=list)
    extra: dict = field(default_factory=dict)

    def to_metadata_dict(self, chosen: MediaFormat | None = None) -> dict:
        data = {
            "platform": self.platform,
            "media_type": self.media_type.value,
            "id": self.id,
            "author": self.author,
            "title": self.title,
            "url": self.source_url,
            "upload_date": self.upload_date,
            "duration": self.duration,
        }
        if chosen is not None:
            data.update(
                {
                    "resolution": chosen.resolution_label,
                    "fps": chosen.fps,
                    "codec": chosen.codec,
                    "format": chosen.extension,
                }
            )
        return data


class Extractor:
    """Base class every platform extractor implements.

    Subclasses only need ``supports()`` and ``extract()``. Extractors
    discover media — they never download it and never write files.
    """

    name: str = "base"

    def supports(self, url: str) -> bool:
        raise NotImplementedError

    def extract(self, url: str) -> MediaInfo | list[MediaInfo]:
        """Return one MediaInfo for a single item, or a list of them
        for galleries/carousels/multi-image posts."""
        raise NotImplementedError

    def extract_profile_picture(self, url: str) -> MediaInfo:
        raise NotImplementedError(f"{self.name} does not support --profile yet.")

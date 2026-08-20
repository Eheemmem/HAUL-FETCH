"""Orchestrates the full per-URL pipeline (spec §29):

    validate -> detect -> select extractor -> extract metadata ->
    discover formats -> rank -> select -> download -> merge if
    needed -> validate -> write metadata if requested -> save

cli.py drives this once per URL; this module has no argparse or
terminal-output concerns of its own, so it's straightforward to
unit-test with a fake extractor and a fake downloader.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from ..utils.filenames import render_filename, safe_join, sanitize_component
from . import errors
from .detector import detect
from .downloader import DuplicatePolicy, DuplicatePrompt, Downloader, ProgressCallback
from .extractor import MediaFormat, MediaInfo
from .metadata import write_metadata
from .registry import Registry
from .selector import select_for_quality

DEFAULT_TEMPLATE = "{platform}_{author}_{id}.{ext}"
AUDIO_EXTENSIONS = {"m4a", "mp3", "aac", "opus", "wav", "ogg"}

OnBatch = Callable[[list[MediaInfo]], None]
OnSelected = Callable[[MediaInfo, MediaFormat], None]


@dataclass
class DownloadRequest:
    url: str
    output_dir: Path
    quality: str = "best"
    duplicate_policy: DuplicatePolicy = "ask"
    want_audio_only: bool = False
    want_profile_picture: bool = False
    want_metadata: bool = False
    filename_template: str | None = None


@dataclass
class DownloadResult:
    info: MediaInfo
    chosen: MediaFormat
    path: Path
    metadata_path: Path | None = None
    skipped: bool = False


def _destination_for(req: DownloadRequest, info: MediaInfo, ext: str) -> Path:
    template = req.filename_template or DEFAULT_TEMPLATE
    filename = render_filename(
        template,
        platform=info.platform,
        author=info.author,
        id=info.id,
        title=info.title,
        ext=ext,
    )
    return safe_join(req.output_dir, (info.platform, sanitize_component(info.author)), filename)


def _select_audio(info: MediaInfo) -> MediaFormat:
    if info.audio_formats:
        return max(info.audio_formats, key=lambda f: f.bitrate or 0)
    if info.formats:
        # No standalone audio stream was exposed — fall back to the
        # best video format and extract its audio track after
        # download (spec §14, "optional conversion... can come later").
        return max(info.formats, key=lambda f: (f.height or 0, f.bitrate or 0))
    raise errors.ExtractionError(url=info.source_url, detail="No audio-capable formats were found for this media.")


def run(
    req: DownloadRequest,
    registry: Registry,
    downloader: Downloader,
    *,
    on_batch: OnBatch | None = None,
    on_selected: OnSelected | None = None,
    on_progress: ProgressCallback | None = None,
    on_duplicate: DuplicatePrompt | None = None,
) -> list[DownloadResult]:
    extractor = detect(req.url, registry)

    if req.want_profile_picture:
        info_items = [extractor.extract_profile_picture(req.url)]
    else:
        extracted = extractor.extract(req.url)
        info_items = extracted if isinstance(extracted, list) else [extracted]

    if on_batch:
        on_batch(info_items)

    return [
        _download_one(req, info, downloader, on_progress=on_progress, on_duplicate=on_duplicate, on_selected=on_selected)
        for info in info_items
    ]


def _download_one(
    req: DownloadRequest,
    info: MediaInfo,
    downloader: Downloader,
    *,
    on_progress: ProgressCallback | None,
    on_duplicate: DuplicatePrompt | None,
    on_selected: OnSelected | None,
) -> DownloadResult:
    if req.want_audio_only:
        chosen = _select_audio(info)
    else:
        if not info.formats:
            raise errors.ExtractionError(url=req.url, detail="No image/video formats were found for this media.")
        chosen = select_for_quality(info.formats, req.quality)

    if on_selected:
        on_selected(info, chosen)

    ext = chosen.extension
    destination = _destination_for(req, info, ext)
    dest = downloader.resolve_destination(destination, policy=req.duplicate_policy, prompt=on_duplicate)
    if dest is None:
        return DownloadResult(info, chosen, destination, skipped=True)

    needs_merge = bool(chosen.audio_url) and not chosen.has_audio and not req.want_audio_only
    if needs_merge:
        video_tmp = dest.with_name(f"{dest.stem}.video.{chosen.extension}")
        audio_tmp = dest.with_name(f"{dest.stem}.audio.{chosen.audio_extension or 'm4a'}")
        downloader.download(chosen.url, video_tmp, on_progress=on_progress)
        downloader.download(chosen.audio_url, audio_tmp, on_progress=on_progress)
        path = downloader.merge_audio_video(video_tmp, audio_tmp, dest)
    else:
        path = downloader.download(chosen.url, dest, on_progress=on_progress)

    if req.want_audio_only and path.suffix.lstrip(".") not in AUDIO_EXTENSIONS:
        # We downloaded a full video because no standalone audio
        # stream existed for this platform — pull the audio track
        # out and drop the video (spec §14).
        audio_path = path.with_suffix(".m4a")
        downloader.extract_audio(path, audio_path)
        path.unlink(missing_ok=True)
        path = audio_path

    metadata_path = write_metadata(info, chosen, path) if req.want_metadata else None
    return DownloadResult(info, chosen, path, metadata_path)

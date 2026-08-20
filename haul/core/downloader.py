"""Downloads a single MediaFormat to disk and drives FFmpeg when
audio/video need muxing (spec §10, §30). This is the only module
that writes media files or invokes FFmpeg — extractors never touch
the network for content, and the selector never touches disk.

Reliability requirements implemented here, straight from spec §30:
  - retry transient network failures
  - resume via HTTP Range when the server supports it
  - validate downloaded size against what the server advertised
  - write to a ``.part`` file first, atomically rename on success
  - never silently overwrite an existing file
"""

from __future__ import annotations

import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal

import requests

from ..utils.network import build_session
from . import errors

DuplicatePolicy = Literal["ask", "force", "skip"]

RETRYABLE_STATUS = {429, 500, 502, 503, 504}
MAX_RETRIES = 3
CHUNK_SIZE = 256 * 1024


@dataclass
class ProgressEvent:
    downloaded: int
    total: int | None
    speed_bps: float


ProgressCallback = Callable[[ProgressEvent], None]
DuplicatePrompt = Callable[[Path], str]  # returns "skip" | "overwrite" | "rename"


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def _next_available_name(path: Path) -> Path:
    counter = 1
    candidate = path
    while candidate.exists():
        candidate = path.with_name(f"{path.stem}_{counter}{path.suffix}")
        counter += 1
    return candidate


class Downloader:
    def __init__(self, session: requests.Session | None = None) -> None:
        self._session = session or build_session()

    def close(self) -> None:
        self._session.close()

    # -- duplicate handling (spec §16) -----------------------------------

    def resolve_destination(
        self,
        destination: Path,
        *,
        policy: DuplicatePolicy,
        prompt: DuplicatePrompt | None = None,
    ) -> Path | None:
        """Returns the path to actually write to, or ``None`` to
        skip. Never silently overwrites."""
        if not destination.exists():
            return destination
        if policy == "force":
            return destination
        if policy == "skip" or prompt is None:
            return None

        choice = prompt(destination)
        if choice == "overwrite":
            return destination
        if choice == "rename":
            return _next_available_name(destination)
        return None

    # -- core streaming download ------------------------------------------

    def download(
        self,
        url: str,
        destination: Path,
        *,
        on_progress: ProgressCallback | None = None,
        headers: dict | None = None,
    ) -> Path:
        """Streams ``url`` to ``destination``. Writes to a
        ``<name>.part`` file first and atomically renames it on
        success. If a partial ``.part`` file already exists (e.g.
        from an interrupted run), resumes it via an HTTP Range
        request when the server allows it.
        """
        destination.parent.mkdir(parents=True, exist_ok=True)
        part_path = destination.with_name(destination.name + ".part")

        last_error: Exception | None = None
        for attempt in range(1, MAX_RETRIES + 1):
            resume_from = part_path.stat().st_size if part_path.exists() else 0
            req_headers = dict(headers or {})
            if resume_from:
                req_headers["Range"] = f"bytes={resume_from}-"
            try:
                return self._download_once(url, part_path, destination, resume_from, req_headers, on_progress)
            except requests.exceptions.HTTPError as e:
                status = e.response.status_code if e.response is not None else None
                if status in RETRYABLE_STATUS and attempt < MAX_RETRIES:
                    last_error = e
                    time.sleep(min(2**attempt, 10))
                    continue
                raise self._classify_http_error(e, url) from e
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout, requests.exceptions.ChunkedEncodingError) as e:
                last_error = e
                if attempt < MAX_RETRIES:
                    time.sleep(min(2**attempt, 10))
                    continue
                raise errors.NetworkError(url=url, detail=str(e)) from e
            except OSError as e:
                if e.errno == 28:  # ENOSPC
                    raise errors.DiskFull(url=url) from e
                if e.errno in (13, 30):  # EACCES, EROFS
                    raise errors.HaulPermissionError(url=url, detail=str(e)) from e
                raise errors.DownloadError(url=url, detail=str(e)) from e

        raise errors.DownloadError(url=url, detail=str(last_error))

    @staticmethod
    def _classify_http_error(e: requests.exceptions.HTTPError, url: str) -> errors.HaulError:
        status = e.response.status_code if e.response is not None else None
        if status == 404:
            return errors.ContentNotFound(url=url)
        if status in (401, 403):
            return errors.PrivateContent(url=url)
        if status == 429:
            return errors.RateLimited(url=url)
        return errors.DownloadError(url=url, detail=str(e))

    def _download_once(
        self,
        url: str,
        part_path: Path,
        final_path: Path,
        resume_from: int,
        headers: dict,
        on_progress: ProgressCallback | None,
    ) -> Path:
        mode = "ab" if resume_from else "wb"
        start = time.monotonic()

        with self._session.get(url, headers=headers, stream=True, timeout=30) as response:
            if response.status_code == 416:
                # Range not satisfiable — the .part file is already
                # complete or stale. Drop it and restart clean.
                part_path.unlink(missing_ok=True)
                return self._download_once(url, part_path, final_path, 0, {}, on_progress)
            response.raise_for_status()

            total: int | None = None
            content_range = response.headers.get("content-range")
            if content_range and "/" in content_range:
                total = int(content_range.rsplit("/", 1)[-1])
            elif "content-length" in response.headers:
                total = resume_from + int(response.headers["content-length"])

            downloaded = resume_from
            with open(part_path, mode) as f:
                for chunk in response.iter_content(CHUNK_SIZE):
                    if not chunk:
                        continue
                    f.write(chunk)
                    downloaded += len(chunk)
                    if on_progress:
                        elapsed = max(time.monotonic() - start, 1e-6)
                        speed = (downloaded - resume_from) / elapsed
                        on_progress(ProgressEvent(downloaded, total, speed))

        actual_size = part_path.stat().st_size
        if total is not None and actual_size != total:
            raise errors.DownloadError(
                url=url,
                detail=f"Downloaded size ({actual_size} bytes) did not match the expected size ({total} bytes).",
            )

        part_path.replace(final_path)  # atomic rename on the same filesystem
        return final_path

    # -- FFmpeg integration (spec §10) ------------------------------------

    def merge_audio_video(self, video_path: Path, audio_path: Path, output_path: Path) -> Path:
        """Muxes a separately-downloaded video and audio stream into
        one file via the system FFmpeg. Never invoked through a
        shell — arguments are passed as an array (spec §31)."""
        if not ffmpeg_available():
            raise errors.FFmpegMissing()
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-i", str(audio_path),
            "-c", "copy",
            "-map", "0:v:0",
            "-map", "1:a:0",
            str(output_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise errors.DownloadError(detail=f"FFmpeg failed to merge audio and video:\n{result.stderr[-800:]}")
        video_path.unlink(missing_ok=True)
        audio_path.unlink(missing_ok=True)
        return output_path

    def extract_audio(self, input_path: Path, output_path: Path) -> Path:
        """Pulls the audio track out of a downloaded video (used for
        ``--audio`` on platforms that don't expose a standalone audio
        stream). Tries a fast stream copy first, falls back to a
        re-encode if the container doesn't support it."""
        if not ffmpeg_available():
            raise errors.FFmpegMissing()

        copy_cmd = ["ffmpeg", "-y", "-i", str(input_path), "-vn", "-acodec", "copy", str(output_path)]
        result = subprocess.run(copy_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            reencode_cmd = [
                "ffmpeg", "-y", "-i", str(input_path),
                "-vn", "-acodec", "aac", "-b:a", "128k", str(output_path),
            ]
            result = subprocess.run(reencode_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise errors.DownloadError(detail=f"FFmpeg failed to extract audio:\n{result.stderr[-800:]}")
        return output_path

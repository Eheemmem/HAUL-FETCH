"""Shared adapter that turns yt-dlp's extraction into HAUL's own
MediaInfo/MediaFormat model.

Why yt-dlp as the extraction engine: hand-rolling scrapers against
Instagram/TikTok/Facebook's private, unversioned endpoints would mean
reverse-engineering signed URLs and anti-bot measures per platform,
and redoing that work every time a platform changes its internal
API — fragile, and it edges toward the "circumvent platform security
mechanisms" behavior the product spec explicitly rules out (§2). Read
from public pages only, do not authenticate, and do not touch DRM;
that's the extraction contract HAUL wants, and it's exactly what
yt-dlp already provides and actively maintains across six platforms.

HAUL still owns everything the spec cares about: yt-dlp is used in
``skip_download`` (probe-only) mode purely to *discover* what exists.
HAUL's own Downloader does the actual fetching, resuming, retrying,
and atomic writes, and HAUL's own selector decides which quality to
use — yt-dlp never touches the filesystem here.
"""

from __future__ import annotations

from urllib.parse import urlparse

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError as YtDlpDownloadError
from yt_dlp.utils import ExtractorError as YtDlpExtractorError

from ..core import errors
from ..core.extractor import Extractor, MediaFormat, MediaInfo, MediaType


def first_match(text: str, *patterns: str) -> str | None:
    """Returns the first regex-group match found across several
    fallback patterns, or None. Used for best-effort scraping of
    small public HTML fragments (e.g. an og:image tag) that don't go
    through yt-dlp."""
    import re

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return None


class YtdlpExtractor(Extractor):
    """Base class for platform extractors backed by yt-dlp.
    Subclasses declare ``name`` and ``domains``, and may override
    ``_media_type_for`` for platform-specific quirks (e.g. treating a
    yt-dlp "playlist" result as a carousel/gallery instead)."""

    domains: tuple[str, ...] = ()

    def supports(self, url: str) -> bool:
        host = urlparse(url).netloc.lower()
        for prefix in ("www.", "m.", "mobile."):
            if host.startswith(prefix):
                host = host[len(prefix):]
        return any(host == d or host.endswith("." + d) for d in self.domains)

    def _ydl_opts(self) -> dict:
        return {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "noplaylist": False,
            "extract_flat": False,
            "ignoreerrors": False,
        }

    def _probe(self, url: str) -> dict:
        try:
            with YoutubeDL(self._ydl_opts()) as ydl:
                data = ydl.extract_info(url, download=False)
        except YtDlpExtractorError as e:
            message = str(e).lower()
            if "private" in message or "login" in message or "sign in" in message:
                raise errors.PrivateContent(url=url, detail=str(e)) from e
            if "not found" in message or "unavailable" in message or "404" in message or "removed" in message:
                raise errors.ContentNotFound(url=url, detail=str(e)) from e
            raise errors.ExtractionError(url=url, detail=str(e)) from e
        except YtDlpDownloadError as e:
            raise errors.ExtractionError(url=url, detail=str(e)) from e

        if data is None:
            raise errors.ContentNotFound(url=url, detail="No media information was returned for this URL.")
        return data

    def extract(self, url: str) -> MediaInfo | list[MediaInfo]:
        data = self._probe(url)
        if data.get("_type") == "playlist" and data.get("entries"):
            entries = [e for e in data["entries"] if e]
            if not entries:
                raise errors.ContentNotFound(url=url, detail="This post has no downloadable items.")
            return [self._to_media_info(url, entry) for entry in entries]
        return self._to_media_info(url, data)

    # -- normalization -----------------------------------------------------

    def _to_media_info(self, source_url: str, data: dict) -> MediaInfo:
        media_type = self._media_type_for(data)
        video_formats, audio_formats = self._formats_from(data, media_type)
        return MediaInfo(
            platform=self.name,
            media_type=media_type,
            id=str(data.get("id") or "unknown"),
            source_url=data.get("webpage_url") or source_url,
            author=data.get("uploader") or data.get("channel") or data.get("uploader_id"),
            title=data.get("title"),
            upload_date=data.get("upload_date"),
            duration=data.get("duration"),
            thumbnail=data.get("thumbnail"),
            formats=video_formats,
            audio_formats=audio_formats,
            extra={"raw_extractor": data.get("extractor")},
        )

    def _media_type_for(self, data: dict) -> MediaType:
        if data.get("vcodec") and data.get("vcodec") != "none":
            return MediaType.VIDEO
        ext = (data.get("ext") or "").lower()
        if ext in {"jpg", "jpeg", "png", "webp", "heic"}:
            return MediaType.IMAGE
        return MediaType.VIDEO

    def _formats_from(self, data: dict, media_type: MediaType) -> tuple[list[MediaFormat], list[MediaFormat]]:
        """Splits yt-dlp's flat format list into video-capable
        formats and standalone audio-only formats. When a video
        format has no attached audio, the best available audio-only
        stream is linked onto it via ``audio_url`` so the downloader
        knows to fetch both and hand them to FFmpeg (spec §10)."""
        raw_formats = data.get("formats") or []

        if not raw_formats:
            is_audio_only = data.get("vcodec") in (None, "none") and data.get("acodec") not in (None, "none")
            single = MediaFormat(
                url=data.get("url"),
                extension=data.get("ext", "bin"),
                width=data.get("width"),
                height=data.get("height"),
                fps=data.get("fps"),
                bitrate=data.get("tbr") or data.get("abr"),
                codec=data.get("vcodec") or data.get("acodec"),
                filesize=data.get("filesize") or data.get("filesize_approx"),
                has_audio=data.get("acodec") not in (None, "none"),
            )
            return ([], [single]) if is_audio_only else ([single], [])

        audio_only_raw = [f for f in raw_formats if f.get("vcodec") in (None, "none") and f.get("acodec") not in (None, "none")]
        audio_formats = [
            MediaFormat(
                url=f.get("url"),
                extension=f.get("ext", "m4a"),
                bitrate=f.get("abr") or f.get("tbr"),
                codec=f.get("acodec"),
                filesize=f.get("filesize") or f.get("filesize_approx"),
                has_audio=True,
            )
            for f in audio_only_raw
        ]
        best_audio = max(audio_formats, key=lambda f: f.bitrate or 0, default=None)

        video_formats = []
        for f in raw_formats:
            if f.get("vcodec") in (None, "none"):
                continue
            has_audio = f.get("acodec") not in (None, "none")
            fmt = MediaFormat(
                url=f.get("url"),
                extension=f.get("ext", "mp4"),
                width=f.get("width"),
                height=f.get("height"),
                fps=f.get("fps"),
                bitrate=f.get("tbr"),
                codec=f.get("vcodec"),
                filesize=f.get("filesize") or f.get("filesize_approx"),
                has_audio=has_audio,
            )
            if not has_audio and best_audio is not None:
                fmt.audio_url = best_audio.url
                fmt.audio_extension = best_audio.extension
            video_formats.append(fmt)

        if not video_formats and audio_formats:
            return [], audio_formats  # pure audio media (e.g. a track/podcast episode)

        return video_formats, audio_formats

    def extract_profile_picture(self, url: str) -> MediaInfo:
        raise errors.ExtractionError(
            url=url,
            detail=f"{self.name.title()} profile pictures aren't supported yet — see the roadmap in README.md.",
        )

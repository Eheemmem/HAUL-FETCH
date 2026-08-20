"""YouTube extractor — videos, Shorts, and audio (spec §3 Tier 1).

YouTube is the canonical case for separate video/audio streams at
high resolution (spec §10): yt-dlp exposes DASH video-only formats
alongside audio-only formats, and ``_shared.py`` links the best
matching audio stream onto each video-only format so the downloader
knows to fetch both and mux them.
"""

from __future__ import annotations

from ._shared import YtdlpExtractor


class YouTubeExtractor(YtdlpExtractor):
    name = "youtube"
    domains = ("youtube.com", "youtu.be", "music.youtube.com")

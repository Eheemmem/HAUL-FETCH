<p style="text-align: center;">

# HAUL
  
</p>

**Paste a URL. Get the best available media. Nothing else.**

HAUL is a privacy-first CLI tool for downloading publicly accessible media
from Instagram, YouTube, Reddit, Pinterest, TikTok, and Facebook — always at
the best quality the source actually exposes, with a clean output structure
and no accounts, tracking, or ads.

```
$ haul https://www.instagram.com/reel/Cx1234567/

Platform    Instagram
Type        Reel
Author      @example
Quality     2160x3840
Format      MP4

Downloading ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 24.3/24.3 MB 8.2 MB/s

✓ Saved:
  downloads/instagram/example/instagram_example_cx1234567.mp4
```

## Install

```bash
pip install -e .          # from a clone of this repo
# or, once published:
pip install haul-cli
```

Requires **Python 3.10+** and, for anything that needs audio/video muxing or
audio extraction (`--audio`, or platforms that serve video and audio as
separate streams), a system install of **[FFmpeg](https://ffmpeg.org/download.html)**
on your `PATH`. Everything else works without it.

## Usage

```bash
# Single URL — downloads the best available quality
haul https://youtube.com/watch?v=dQw4w9WgXcQ

# Multiple URLs at once (processed concurrently)
haul https://instagram.com/reel/abc https://reddit.com/r/x/comments/y

# From a text file, one URL per line (# comments allowed)
haul --file urls.txt

# Cap the quality instead of always taking the best
haul -q 1080p https://youtube.com/watch?v=dQw4w9WgXcQ

# Audio only
haul --audio https://youtube.com/watch?v=dQw4w9WgXcQ

# Custom output directory
haul -o ~/Downloads/clips https://tiktok.com/@user/video/123

# Write a JSON metadata sidecar next to the file
haul --metadata https://reddit.com/r/x/comments/y

# A profile picture instead of a post (Instagram only for now)
haul --profile https://instagram.com/example

# Custom filename template
haul --filename "{author}_{title}.{ext}" https://youtube.com/watch?v=dQw4w9WgXcQ

# Non-interactive batch runs
haul --file urls.txt --skip-existing   # never prompt, never overwrite
haul --file urls.txt --force           # never prompt, always overwrite
```

Run `haul --help` for the full flag reference.

### Output structure

```
downloads/
├── instagram/
│   └── example/
│       ├── instagram_example_cx1234567.mp4
│       └── instagram_example_cx1234567.json   (with --metadata)
├── youtube/
│   └── creator/
│       └── youtube_creator_dqw4w9wgxcq.mp4
```

### Duplicate files

HAUL never silently overwrites a file. If the destination already exists:

- In an interactive terminal with a single URL, you're prompted:
  **[1] Skip [2] Overwrite [3] Rename**.
- In a batch run (multiple URLs, `--file`, or non-interactive), it defaults
  to **skip** — the safe choice — unless you pass `--force` or
  `--skip-existing` explicitly.

### Config file

HAUL works with zero configuration. To set your own defaults, copy
[`config.example.toml`](config.example.toml) to `~/.config/haul/config.toml`:

```toml
output = "~/Downloads/haul"
quality = "best"
metadata = false
concurrency = 3
```

Any CLI flag always overrides the config file.

## Supported platforms

| Platform  | Video | Image | Gallery/Carousel | Audio-only | Profile picture |
|-----------|:-----:|:-----:|:-----------------:|:----------:|:----------------:|
| Instagram |   ✓   |   ✓   |         ✓          |     ✓      |        ✓         |
| YouTube   |   ✓   |   —   |         —          |     ✓      |        —         |
| Reddit    |   ✓   |   ✓   |         ✓          |     ✓      |        —         |
| Pinterest |   ✓   |   ✓   |         —          |     ✓      |        —         |
| TikTok    |   ✓   |   ✓   |         ✓          |     ✓      |        —         |
| Facebook  |   ✓   |   ✓   |         —          |     ✓      |        —         |

HAUL only ever reads **publicly accessible** content. It never logs in,
never bypasses a login wall, and never touches DRM-protected media — if a
post is private, you'll get a clear error, not a workaround.

## Architecture

Every layer only knows about the layer below it: extractors never touch the
filesystem, the selector never touches the network, and the downloader never
knows what platform a URL came from. Adding a platform means writing one
file in `extractors/` and registering it in
`core/registry.build_default_registry()` — nothing else changes.

### Why yt-dlp as the extraction engine

Six platforms means six different private, unversioned front-end APIs, each
with its own anti-bot measures and signed-URL schemes that change without
notice. Hand-rolling that from scratch would be fragile, would need
constant reverse-engineering, and would start to look less like "read a
public page" and more like "circumvent a platform's protections" — which is
explicitly out of scope for this tool.

**yt-dlp** already solves exactly this problem, for exactly these platforms,
and does so by reading public pages — it doesn't authenticate, and it
doesn't touch DRM. HAUL uses it strictly as a *discovery* engine
(`skip_download=True` — it only asks "what formats exist?"). Every other
guarantee in this spec — resumable/atomic downloads, retry logic, quality
selection, output structure, filename safety, duplicate handling — is
HAUL's own code in `core/`, not yt-dlp's. If you'd rather see raw
per-platform scrapers, `extractors/_shared.py` is the one place that would
need to change; the rest of the architecture doesn't care how extraction
happens.

## Testing

```bash
pip install -e ".[dev]"
pytest
```

- `tests/test_selector.py` — quality ranking, including the never-upscale rule
- `tests/test_filenames.py` — sanitization and path-traversal safety
- `tests/test_detector.py` — URL validation and platform routing
- `tests/test_downloader.py` — real streaming/resume/atomic-write behavior
  against a local HTTP server (no mocking of `requests`)
- `tests/test_pipeline.py` — full pipeline wiring with fake extractor/downloader
- `tests/test_config.py`, `tests/test_errors.py` — config loading, error rendering
- `tests/extractors/test_supports.py` — each extractor's URL-matching logic
- `tests/test_regressions.py` — one test per bug found in the wild; add to
  this file whenever a platform quirk breaks something

## Known limitations

- **Instagram profile pictures** are read by pattern-matching Instagram's
  public HTML, since yt-dlp doesn't expose that field. Instagram's markup
  changes without notice, so this is best-effort — if it stops working,
  see `extractors/instagram.py:extract_profile_picture`.
- **Live streams, Stories, and age/login-gated content** are out of scope —
  HAUL only downloads content a platform serves without authentication.
- Extraction correctness for any given platform is only as good as the
  installed `yt-dlp` version. If a platform changes its page structure and
  extraction starts failing, `pip install -U yt-dlp` first.

## Non-goals

HAUL deliberately does **not**: log in or use cookies/sessions, download
private or authenticated content, circumvent DRM or platform security
measures, batch-scrape entire accounts, or edit/transcode video beyond the
audio extraction and audio/video muxing needed to assemble a single
already-selected quality tier.

## License

MIT — see [LICENSE](LICENSE).

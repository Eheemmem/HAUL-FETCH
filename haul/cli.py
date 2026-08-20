"""Command-line entry point (spec §27, §28).

Parses arguments, builds one DownloadRequest per URL, and renders
output. No extraction, selection, or download logic lives here —
only orchestration and presentation, so the pipeline stays testable
without a terminal attached.
"""

from __future__ import annotations

import concurrent.futures
import sys
from pathlib import Path

from . import __version__
from .config import load_config
from .core import errors
from .core.downloader import Downloader
from .core.extractor import MediaFormat, MediaInfo
from .core.pipeline import DownloadRequest, DownloadResult, run
from .core.registry import build_default_registry
from .utils import progress as ui

QUALITY_CHOICES = ["best", "2160p", "1440p", "1080p", "720p", "480p", "360p"]
LABEL_WIDTH = 42


def build_parser():
    import argparse

    parser = argparse.ArgumentParser(
        prog="haul",
        description="Paste a URL. Get the best available media. Nothing else.",
        epilog="Supported platforms: Instagram, YouTube, Reddit, Pinterest, TikTok, Facebook.",
    )
    parser.add_argument("urls", nargs="*", metavar="URL", help="One or more public media URLs to download.")
    parser.add_argument("--file", "-F", dest="file", metavar="PATH", help="Read URLs from a text file, one per line.")
    parser.add_argument("--output", "-o", dest="output", metavar="DIR", help="Destination directory (default: ./downloads).")
    parser.add_argument("--quality", "-q", dest="quality", choices=QUALITY_CHOICES, help="Maximum quality to download (default: best).")
    parser.add_argument("--audio", action="store_true", help="Extract audio only.")
    parser.add_argument("--profile", action="store_true", help="Download the profile picture for a profile URL instead of a post.")
    parser.add_argument("--metadata", action="store_true", help="Write a JSON metadata sidecar file next to each download.")
    parser.add_argument("--filename", dest="filename_template", metavar="TEMPLATE", help='Custom filename template, e.g. "{author}_{title}.{ext}".')
    parser.add_argument("--force", "-f", action="store_true", help="Overwrite files that already exist.")
    parser.add_argument("--skip-existing", action="store_true", help="Skip files that already exist without prompting.")
    parser.add_argument("--concurrency", type=int, default=None, metavar="N", help="Number of URLs to process at once (default: 3).")
    parser.add_argument("--quiet", action="store_true", help="Suppress non-essential output.")
    parser.add_argument("--verbose", action="store_true", help="Print extra diagnostic detail.")
    parser.add_argument("--version", action="version", version=f"haul {__version__}")
    return parser


def _prompt_duplicate(path: Path) -> str:
    ui.console.print(f"[yellow]⚠ File already exists:[/yellow] {path}")
    ui.console.print("[1] Skip  [2] Overwrite  [3] Rename")
    while True:
        try:
            choice = input("> ").strip()
        except EOFError:
            return "skip"
        if choice in ("1", ""):
            return "skip"
        if choice == "2":
            return "overwrite"
        if choice == "3":
            return "rename"
        ui.console.print("Please enter 1, 2, or 3.")


def _collect_urls(args) -> list[str]:
    urls = list(args.urls)
    if args.file:
        path = Path(args.file).expanduser()
        if not path.exists():
            ui.error(errors.InvalidURL(detail=f"Batch file not found: {path}").render())
            return []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                urls.append(line)
    return urls


def _duplicate_policy(args, num_urls: int) -> str:
    if args.force:
        return "force"
    if args.skip_existing:
        return "skip"
    # Interactive prompting only makes sense for a single URL at a
    # time in a real terminal; batches default to the safe choice
    # (skip) rather than silently overwriting (spec §30).
    if num_urls == 1 and sys.stdin.isatty() and not args.quiet:
        return "ask"
    return "skip"


def _make_request(url: str, args, config, output_dir: Path, num_urls: int) -> DownloadRequest:
    return DownloadRequest(
        url=url,
        output_dir=output_dir,
        quality=args.quality or config.quality,
        duplicate_policy=_duplicate_policy(args, num_urls),
        want_audio_only=args.audio,
        want_profile_picture=args.profile,
        want_metadata=args.metadata or config.metadata,
        filename_template=args.filename_template,
    )


def _short_label(url: str) -> str:
    return url if len(url) <= LABEL_WIDTH else url[: LABEL_WIDTH - 1] + "…"


def _run_one(url: str, args, config, output_dir: Path, registry, num_urls: int, progress, task_id) -> tuple[str, list[DownloadResult] | None, Exception | None]:
    downloader = Downloader()
    state = {"index": 0, "total": 1}

    def on_batch(items: list[MediaInfo]) -> None:
        state["total"] = len(items)
        if not args.quiet and len(items) > 1:
            ui.info(f"Found {len(items)} items", quiet=args.quiet)

    def on_selected(info: MediaInfo, chosen: MediaFormat) -> None:
        state["index"] += 1
        if args.quiet:
            return
        if state["total"] > 1:
            progress.update(task_id, description=f"[cyan][{state['index']}/{state['total']}] {info.platform.title()}")
        else:
            ui.print_item_header(
                platform=info.platform,
                media_type=info.media_type.value,
                author=info.author,
                quality=chosen.quality_label,
                fmt=chosen.extension.upper(),
            )
            if args.verbose:
                ui.console.print(
                    f"[dim]codec={chosen.codec or '?'} bitrate={chosen.bitrate or '?'} "
                    f"filesize={chosen.filesize or '?'} source={info.source_url}[/dim]"
                )
            progress.update(task_id, description=f"[cyan]{info.platform.title()}")

    def on_progress(event) -> None:
        progress.update(task_id, completed=event.downloaded, total=event.total)

    try:
        req = _make_request(url, args, config, output_dir, num_urls)
        prompt = _prompt_duplicate if req.duplicate_policy == "ask" else None
        results = run(req, registry, downloader, on_batch=on_batch, on_selected=on_selected, on_progress=on_progress, on_duplicate=prompt)
        progress.update(task_id, description=f"[green]✓ {_short_label(url)}")
        return url, results, None
    except errors.HaulError as e:
        progress.update(task_id, description=f"[red]✗ {_short_label(url)}")
        return url, None, e
    except Exception as e:  # pragma: no cover - defensive catch-all
        progress.update(task_id, description=f"[red]✗ {_short_label(url)}")
        return url, None, errors.HaulError(url=url, detail=str(e))
    finally:
        downloader.close()


def _print_result(results: list[DownloadResult] | None, error: Exception | None, quiet: bool) -> None:
    if error is not None:
        ui.error(error.render() if isinstance(error, errors.HaulError) else str(error))
        return
    for result in results or []:
        if result.skipped:
            ui.skipped(result.path)
            continue
        ui.success(result.path)
        if result.metadata_path:
            ui.info(f"  {result.metadata_path}", quiet=quiet)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    config = load_config()
    urls = _collect_urls(args)
    if not urls:
        parser.print_help()
        return 1

    output_dir = Path(args.output or config.output).expanduser()
    registry = build_default_registry()
    concurrency = max(1, args.concurrency if args.concurrency is not None else config.concurrency)
    if len(urls) == 1:
        concurrency = 1

    ui.info(f"HAUL v{__version__}", quiet=args.quiet)
    if args.verbose and not args.quiet:
        ui.console.print(
            f"[dim]output={output_dir} quality={args.quality or config.quality} "
            f"concurrency={concurrency} urls={len(urls)}[/dim]"
        )

    exit_code = 0
    # Progress bars share `ui.console`, so ordinary console.print()
    # calls from _print_result (called as each future completes)
    # correctly print above the live bars instead of clobbering them.
    with ui.make_progress(quiet=args.quiet) as progress:
        task_ids = {url: progress.add_task(_short_label(url), total=None) for url in urls}
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = {
                pool.submit(_run_one, url, args, config, output_dir, registry, len(urls), progress, task_ids[url]): url
                for url in urls
            }
            for future in concurrent.futures.as_completed(futures):
                _, results, error = future.result()
                _print_result(results, error, args.quiet)
                if error is not None:
                    exit_code = 1

    return exit_code


if __name__ == "__main__":
    sys.exit(main())

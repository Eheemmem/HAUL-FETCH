"""Terminal UI (spec §17, "Progress Interface").

Kept intentionally thin — HAUL is a CLI tool, not a TUI framework.
This wraps `rich` just enough to reproduce the product spec's mock
output (the Platform/Type/Author/Quality/Format block, a progress
bar with speed and ETA, and per-item batch rows) without pulling in
a heavier dependency. "Avoid excessive animations or UI" (spec §17)
is honored by using rich's plain, non-flashy default styling.
"""

from __future__ import annotations

from rich.console import Console
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

console = Console()
err_console = Console(stderr=True)


def print_item_header(
    *,
    platform: str,
    media_type: str,
    author: str | None,
    quality: str,
    fmt: str,
    quiet: bool = False,
) -> None:
    """Reproduces the spec §4 header block:

        Platform    Instagram
        Type        Reel
        Author      @example
        Quality     2160x3840
        Format      MP4
    """
    if quiet:
        return
    console.print()
    console.print(f"[dim]Platform[/dim]    {platform.title()}")
    console.print(f"[dim]Type[/dim]        {media_type.replace('_', ' ').title()}")
    if author:
        console.print(f"[dim]Author[/dim]      @{author}")
    console.print(f"[dim]Quality[/dim]     {quality}")
    console.print(f"[dim]Format[/dim]      {fmt}")
    console.print()


def make_progress(*, quiet: bool = False) -> Progress:
    return Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
        console=console,
        disable=quiet,
        transient=False,
    )


def success(path) -> None:
    console.print(f"[bold green]✓ Saved:[/bold green]\n  {path}")


def skipped(path) -> None:
    console.print(f"[yellow]⚠ Skipped (already exists):[/yellow] {path}")


def warn(message: str) -> None:
    err_console.print(f"[bold yellow]⚠[/bold yellow] {message}")


def error(rendered_message: str) -> None:
    err_console.print(f"[bold red]{rendered_message}[/bold red]")


def info(message: str, *, quiet: bool = False) -> None:
    if not quiet:
        console.print(message)

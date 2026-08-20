"""Filename sanitization and templating (spec §9).

Every filename or directory component HAUL writes passes through
here — this is where the "never let a remote title escape the
download directory" security requirement (spec §31) is enforced.
A malicious title like ``../../../../home/user/.bashrc`` becomes a
harmless, safe slug rather than a path-traversal vector.
"""

from __future__ import annotations

import re
from pathlib import Path

_UNSAFE_CHARS = re.compile(r"[^a-z0-9]+")
_REPEATED_UNDERSCORE = re.compile(r"_+")
MAX_COMPONENT_LENGTH = 80

DEFAULT_TEMPLATE = "{platform}_{author}_{id}"

# Placeholders a filename template is allowed to reference. Anything
# else is rejected so a template can never reach into internals.
ALLOWED_TEMPLATE_FIELDS = {"platform", "author", "id", "title", "ext"}


def slugify(text: str, max_length: int = MAX_COMPONENT_LENGTH) -> str:
    """Lowercase, ASCII-only, underscore-separated slug. Strips any
    path separators, traversal sequences, and punctuation. Empty or
    fully-stripped input falls back to 'untitled' so callers never
    end up with an empty path component.

    >>> slugify("How I Built My PC: Part 1!")
    'how_i_built_my_pc_part_1'
    >>> slugify("../../../../home/user/.bashrc")
    'home_user_bashrc'
    """
    text = text.strip().lower()
    text = _UNSAFE_CHARS.sub("_", text)
    text = _REPEATED_UNDERSCORE.sub("_", text).strip("_")
    if not text:
        return "untitled"
    return text[:max_length].rstrip("_") or "untitled"


def sanitize_component(value: str | None, fallback: str = "unknown") -> str:
    """Slugifies a single path component (author, platform, id),
    substituting ``fallback`` when the value is missing."""
    if not value:
        return fallback
    return slugify(value)


def render_filename(
    template: str,
    *,
    platform: str,
    author: str | None,
    id: str,
    title: str | None,
    ext: str,
) -> str:
    """Renders a filename template (spec §9, e.g.
    ``"{author}_{title}.{ext}"``). Only whitelisted fields are ever
    substituted, and every substituted value is slugified first, so a
    hostile title or author can never inject a path separator,
    traversal sequence, or unknown template internals. An invalid or
    unknown placeholder falls back to the safe default template
    rather than failing the whole download.
    """
    values = {
        "platform": sanitize_component(platform),
        "author": sanitize_component(author),
        "id": sanitize_component(id),
        "title": sanitize_component(title, fallback=sanitize_component(id)),
        "ext": ext.lstrip("."),
    }

    referenced = set(re.findall(r"{(\w*)}", template))
    if not referenced <= ALLOWED_TEMPLATE_FIELDS:
        template = DEFAULT_TEMPLATE + ".{ext}"

    try:
        name = template.format(**values)
    except (KeyError, IndexError, ValueError):
        name = (DEFAULT_TEMPLATE + ".{ext}").format(**values)

    if not name.strip():
        name = (DEFAULT_TEMPLATE + ".{ext}").format(**values)
    return name


def safe_join(base: Path, dir_parts: tuple[str, ...] | list[str], filename: str) -> Path:
    """Builds ``base/dir_parts.../filename``.

    Directory components (platform, author) are slugified. The
    filename is expected to already be a rendered, safe name (from
    :func:`render_filename` or the default template) — it is passed
    through :func:`pathlib.PurePath.name`, which strips any
    directory structure (``/``, ``\\``, ``..``) out of it regardless
    of content, so a hostile filename can never escape ``base``
    without mangling a legitimate ``.`` in the extension.

    Raises ``ValueError`` if, despite all of the above, the resolved
    path would still land outside ``base`` — defense in depth.
    """
    base = base.expanduser().resolve()
    candidate = base
    for part in dir_parts:
        candidate = candidate / sanitize_component(part)

    safe_name = Path(filename).name
    if not safe_name or safe_name in (".", ".."):
        safe_name = "untitled"
    candidate = candidate / safe_name

    resolved = candidate.resolve()
    if resolved != base and base not in resolved.parents:
        raise ValueError(f"Refusing to write outside of {base}: {resolved}")
    return resolved

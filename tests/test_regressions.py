"""Regression tests (spec §32): every platform bug that gets fixed
should get a test here so it can't silently come back. This file
starts with a couple of concrete examples of the pattern; add one
per bug as they're found.
"""

from __future__ import annotations

from haul.utils.filenames import render_filename, slugify


def test_regression_unicode_only_title_does_not_crash():
    # A title made entirely of characters slugify() strips (emoji,
    # certain scripts) must fall back to "untitled" instead of
    # raising or producing an empty filename.
    name = render_filename("{title}.{ext}", platform="p", author="a", id="1", title="🔥🔥🔥", ext="mp4")
    assert name  # non-empty
    assert name.endswith(".mp4")


def test_regression_slugify_handles_non_ascii_gracefully():
    # Non-Latin titles shouldn't crash; they collapse to "untitled"
    # rather than raising, since the current slugify is ASCII-only.
    result = slugify("日本語のタイトル")
    assert result == "untitled"


def test_regression_author_with_at_symbol_is_not_duplicated():
    # Some platforms return the author already prefixed with '@' —
    # the rendered filename shouldn't end up with '@' baked into a
    # slug in a confusing way (it should just be stripped, since '@'
    # isn't a-z0-9).
    name = render_filename("{author}_{id}.{ext}", platform="p", author="@example", id="1", title=None, ext="mp4")
    assert name == "example_1.mp4"

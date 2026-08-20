"""Unit tests for haul.utils.filenames, including the path-traversal
protection required by spec §31."""

from __future__ import annotations

from pathlib import Path

import pytest

from haul.utils.filenames import render_filename, safe_join, sanitize_component, slugify


def test_slugify_basic_title():
    assert slugify("How I Built My PC: Part 1!") == "how_i_built_my_pc_part_1"


def test_slugify_collapses_repeated_separators():
    assert slugify("a   b---c") == "a_b_c"


def test_slugify_empty_input_falls_back():
    assert slugify("   ...   ") == "untitled"


def test_slugify_truncates_long_input():
    result = slugify("x" * 500)
    assert len(result) <= 80


def test_sanitize_component_uses_fallback_for_missing_value():
    assert sanitize_component(None) == "unknown"
    assert sanitize_component("", fallback="anon") == "anon"


def test_render_filename_default_template():
    name = render_filename("{platform}_{author}_{id}.{ext}", platform="instagram", author="example", id="ABC123", title=None, ext="mp4")
    assert name == "instagram_example_abc123.mp4"


def test_render_filename_custom_template():
    name = render_filename("{author}_{title}.{ext}", platform="youtube", author="creator", id="xyz", title="My Video!", ext="mp4")
    assert name == "creator_my_video.mp4"


def test_render_filename_rejects_unknown_placeholder():
    # A template referencing a field HAUL doesn't expose should fall
    # back to the safe default rather than raising or leaking data.
    name = render_filename("{__class__}.{ext}", platform="instagram", author="a", id="1", title=None, ext="mp4")
    assert name == "instagram_a_1.mp4"


def test_render_filename_sanitizes_hostile_title():
    # A title crafted to look like a path-traversal sequence must
    # never survive into the rendered filename unsanitized.
    name = render_filename(
        "{title}.{ext}",
        platform="instagram",
        author="a",
        id="1",
        title="../../../../home/user/.bashrc",
        ext="mp4",
    )
    assert "/" not in name
    assert ".." not in name


def test_safe_join_stays_within_base(tmp_path):
    result = safe_join(tmp_path, ("instagram", "example"), "reel_abc123.mp4")
    assert tmp_path in result.parents
    assert result.name == "reel_abc123.mp4"


def test_safe_join_sanitizes_directory_components(tmp_path):
    result = safe_join(tmp_path, ("../../etc", "passwd"), "video.mp4")
    assert tmp_path.resolve() in result.parents


def test_safe_join_strips_traversal_from_filename(tmp_path):
    result = safe_join(tmp_path, ("instagram",), "../../../etc/passwd")
    assert tmp_path.resolve() in result.parents
    assert result.name == "passwd"


def test_safe_join_preserves_extension_dot(tmp_path):
    result = safe_join(tmp_path, ("youtube",), "how_i_built_my_pc.mp4")
    assert result.suffix == ".mp4"

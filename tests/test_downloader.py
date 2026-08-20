"""Integration tests for haul.core.downloader against a real local
HTTP server (spec §30: retry, resume via Range, atomic writes, never
silently overwrite). This deliberately does not mock `requests` — it
exercises the real streaming/resume code path over loopback, which
is the part of HAUL most worth testing against real bytes rather
than a mock.
"""

from __future__ import annotations

import http.server
import threading
from contextlib import contextmanager

import pytest

from haul.core import errors
from haul.core.downloader import Downloader

CONTENT = b"0123456789" * 1000  # 10,000 bytes


class _RangeHandler(http.server.BaseHTTPRequestHandler):
    content = CONTENT

    def do_GET(self):
        body = self.content
        range_header = self.headers.get("Range")
        if range_header:
            start = int(range_header.split("=")[1].split("-")[0])
            chunk = body[start:]
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{len(body) - 1}/{len(body)}")
            self.send_header("Content-Length", str(len(chunk)))
            self.end_headers()
            self.wfile.write(chunk)
        else:
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    def log_message(self, *args):  # silence request logging
        pass


class _NotFoundHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(404)
        self.end_headers()

    def log_message(self, *args):
        pass


@contextmanager
def _serve(handler_cls):
    server = http.server.HTTPServer(("127.0.0.1", 0), handler_cls)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.shutdown()
        thread.join(timeout=2)


def test_download_full_file(tmp_path):
    with _serve(_RangeHandler) as base_url:
        downloader = Downloader()
        dest = tmp_path / "out.bin"
        result = downloader.download(f"{base_url}/file.bin", dest)
        downloader.close()

    assert result == dest
    assert dest.read_bytes() == CONTENT
    assert not dest.with_name(dest.name + ".part").exists()


def test_download_reports_progress(tmp_path):
    events = []
    with _serve(_RangeHandler) as base_url:
        downloader = Downloader()
        downloader.download(f"{base_url}/file.bin", tmp_path / "out.bin", on_progress=events.append)
        downloader.close()

    assert events
    assert events[-1].downloaded == len(CONTENT)
    assert events[-1].total == len(CONTENT)


def test_download_resumes_partial_file(tmp_path):
    dest = tmp_path / "out.bin"
    part = dest.with_name(dest.name + ".part")
    part.parent.mkdir(parents=True, exist_ok=True)
    part.write_bytes(CONTENT[:4000])  # simulate an interrupted previous run

    with _serve(_RangeHandler) as base_url:
        downloader = Downloader()
        downloader.download(f"{base_url}/file.bin", dest)
        downloader.close()

    assert dest.read_bytes() == CONTENT
    assert not part.exists()


def test_download_raises_content_not_found_on_404(tmp_path):
    with _serve(_NotFoundHandler) as base_url:
        downloader = Downloader()
        with pytest.raises(errors.ContentNotFound):
            downloader.download(f"{base_url}/missing.bin", tmp_path / "out.bin")
        downloader.close()


def test_duplicate_policy_skip_does_not_touch_existing_file(tmp_path):
    dest = tmp_path / "out.bin"
    dest.write_bytes(b"already here")
    downloader = Downloader()
    resolved = downloader.resolve_destination(dest, policy="skip")
    downloader.close()

    assert resolved is None
    assert dest.read_bytes() == b"already here"


def test_duplicate_policy_force_overwrites(tmp_path):
    dest = tmp_path / "out.bin"
    dest.write_bytes(b"stale")
    with _serve(_RangeHandler) as base_url:
        downloader = Downloader()
        resolved = downloader.resolve_destination(dest, policy="force")
        assert resolved == dest
        downloader.download(f"{base_url}/file.bin", resolved)
        downloader.close()

    assert dest.read_bytes() == CONTENT


def test_duplicate_policy_rename_creates_sibling_file(tmp_path):
    dest = tmp_path / "out.bin"
    dest.write_bytes(b"existing")
    downloader = Downloader()
    resolved = downloader.resolve_destination(dest, policy="ask", prompt=lambda p: "rename")
    downloader.close()

    assert resolved == tmp_path / "out_1.bin"


def test_duplicate_policy_ask_without_prompt_defaults_to_skip(tmp_path):
    # A non-interactive environment with no prompt callback must
    # never silently overwrite (spec §30).
    dest = tmp_path / "out.bin"
    dest.write_bytes(b"existing")
    downloader = Downloader()
    resolved = downloader.resolve_destination(dest, policy="ask", prompt=None)
    downloader.close()

    assert resolved is None
    assert dest.read_bytes() == b"existing"

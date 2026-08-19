"""static_server 单元测试（无需 GUI / 浏览器）。"""

import os
import urllib.request

import pytest

from core.static_server import StaticServer, resolve_index

DEMO = os.path.join(os.path.dirname(__file__), "..", "examples", "demo")


def test_resolve_index_finds_index():
    assert resolve_index(DEMO) == "index.html"


def test_resolve_index_missing(tmp_path):
    assert resolve_index(str(tmp_path)) is None


def test_resolve_index_single_html(tmp_path):
    (tmp_path / "page.html").write_text("<html></html>", encoding="utf-8")
    assert resolve_index(str(tmp_path)) == "page.html"


def test_static_server_roundtrip():
    srv = StaticServer(DEMO)
    srv.start()
    try:
        with urllib.request.urlopen(srv.base_url + "/index.html", timeout=5) as resp:
            body = resp.read().decode("utf-8")
        assert "Website Page to Image" in body
    finally:
        srv.stop()


def test_static_server_bad_dir():
    srv = StaticServer(os.path.join(DEMO, "not_exist"))
    with pytest.raises(NotADirectoryError):
        srv.start()
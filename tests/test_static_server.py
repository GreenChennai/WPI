"""static_server 单元测试（无需 GUI / 浏览器）。"""

import os
import urllib.request

import pytest

from core.static_server import StaticServer, list_html_files, resolve_index

DEMO = os.path.join(os.path.dirname(__file__), "..", "examples", "demo")


def test_resolve_index_finds_index():
    assert resolve_index(DEMO) == "index.html"


def test_resolve_index_missing(tmp_path):
    assert resolve_index(str(tmp_path)) is None


def test_resolve_index_single_html(tmp_path):
    (tmp_path / "page.html").write_text("<html></html>", encoding="utf-8")
    assert resolve_index(str(tmp_path)) == "page.html"


def test_resolve_index_prefers_index_over_other_html(tmp_path):
    """v1.7.0：存在 index.html 时它永远是入口，即使有其他 html。"""
    (tmp_path / "index2.html").write_text("<html></html>", encoding="utf-8")
    (tmp_path / "index.html").write_text("<html></html>", encoding="utf-8")
    assert resolve_index(str(tmp_path)) == "index.html"


def test_list_html_files_sorted(tmp_path):
    """v1.7.0：列出目录内全部 HTML（按名称排序），供卡片下拉框使用。"""
    for name in ("index.html", "index3.html", "index2.html", "page.htm", "note.txt"):
        (tmp_path / name).write_text("x", encoding="utf-8")
    assert list_html_files(str(tmp_path)) == [
        "index.html", "index2.html", "index3.html", "page.htm",
    ]


def test_list_html_files_missing(tmp_path):
    assert list_html_files(str(tmp_path)) == []


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
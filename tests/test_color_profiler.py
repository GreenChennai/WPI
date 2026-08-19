"""颜色主色提取（color_profiler）单元测试。"""

import os

from core.color_profiler import clear_cache, extract_palette


def _write(root: str, rel: str, text: str) -> str:
    fp = os.path.join(root, rel)
    os.makedirs(os.path.dirname(fp), exist_ok=True)
    with open(fp, "w", encoding="utf-8") as fh:
        fh.write(text)
    return fp


def _project(tmp_path, name="site") -> str:
    d = os.path.join(str(tmp_path), name)
    _write(d, "index.html", "<html><body style='background:#4a6cf7; color:white'></body></html>")
    _write(d, "css/style.css", ".btn{background:#4a6cf7; border:1px solid #4a6cf7;}\n.bg{background:#7b96ff;}")
    _write(d, "app.js", "const c='#4a6cf7'; const d='#1d2233';")
    clear_cache()
    return d


def test_extract_palette_returns_dominant(tmp_path):
    colors = extract_palette(_project(tmp_path), top=4)
    assert colors, "应至少提取到颜色"
    assert colors[0].lower() == "#4a6cf7"
    assert all(c.startswith("#") for c in colors)


def test_extract_palette_top_limit(tmp_path):
    clear_cache()
    d = _project(tmp_path)
    colors = extract_palette(d, top=2)
    assert len(colors) <= 2


def test_extract_palette_caches_same_result(tmp_path):
    d = _project(tmp_path)
    a = extract_palette(d, top=4)
    b = extract_palette(d, top=4)
    assert a == b


def test_extract_palette_skips_binary_and_empty():
    import tempfile

    d = tempfile.mkdtemp(prefix="empty_proj_")
    assert extract_palette(d, top=4) == []
    clear_cache()


def test_ignores_excluded_dirs(tmp_path):
    d = os.path.join(str(tmp_path), "proj")
    _write(d, "node_modules/x/app.js", "const c='#ff0000'")
    _write(d, "index.html", "<p style='color:#00ff00'>ok</p>")
    clear_cache()
    colors = extract_palette(d, top=4)
    assert "#ff0000" not in colors
    assert colors[0] == "#00ff00"
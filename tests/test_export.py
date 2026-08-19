"""controller / gif_exporter 单元测试。"""

import io
import os

from PIL import Image

from core.controller import ExportParams, build_url


class _FakeServer:
    base_url = "http://127.0.0.1:12345"


def _solid(rgb, size=(64, 64)):
    return Image.new("RGB", size, rgb)


def _frames(n=8):
    return [_solid((i * 20, 20, 200 - i * 20)) for i in range(n)]


def test_gif_pillow_writes(tmp_path):
    from export.gif_exporter import GIFExporter

    out = tmp_path / "out.gif"
    res = GIFExporter(ffmpeg=None).write(
        _frames(), str(out), fps=10, loop=0, use_ffmpeg=False
    )
    assert out.exists() and out.stat().st_size > 0
    im = Image.open(out)
    assert getattr(im, "n_frames", 1) == 8
    assert res["encoder"] == "Pillow"


def test_gif_fallback_when_ffmpeg_missing(tmp_path):
    from export.gif_exporter import GIFExporter

    out = tmp_path / "fallback.gif"
    exporter = GIFExporter(ffmpeg=None)  # 强制无 FFmpeg
    res = exporter.write(_frames(5), str(out), fps=12, loop=0, use_ffmpeg=True)
    assert out.exists()
    assert "Pillow" in res["encoder"]


def test_build_url_file():
    demo = os.path.join(os.path.dirname(__file__), "..", "examples", "demo")
    srv = _FakeServer()
    url = build_url(os.path.join(demo, "index.html"), srv)
    assert url == "http://127.0.0.1:12345/index.html"


def test_build_url_dir_uses_index():
    demo = os.path.join(os.path.dirname(__file__), "..", "examples", "demo")
    srv = _FakeServer()
    url = build_url(demo, srv)
    assert url == "http://127.0.0.1:12345/index.html"


def test_png_transparency_flatten():
    from PIL import Image
    from export.png_exporter import PNGExporter

    img = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
    buf = io.BytesIO()
    PNGExporter.write(img, buf, transparent=False)
    out = Image.open(buf)
    assert out.mode == "RGB"
    assert out.getpixel((5, 5)) == (255, 255, 255)


def test_export_params_full_page_default():
    p = ExportParams(source="x.html")
    assert p.full_page is True


def test_export_params_full_page_off():
    p = ExportParams(source="x.html", format="PNG", full_page=False)
    assert p.full_page is False


def test_unique_path_adds_suffix(tmp_path):
    from core.controller import _unique_path

    target = str(tmp_path / "out.png")
    # 目标不存在 → 原样返回
    assert _unique_path(target) == target
    # 目标存在 → 依次取 out_1.png / out_2.png
    open(target, "w").close()
    p1 = _unique_path(target)
    assert p1.endswith("out_1.png")
    open(p1, "w").close()
    p2 = _unique_path(target)
    assert p2.endswith("out_2.png")
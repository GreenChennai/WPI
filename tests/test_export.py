"""controller / gif_exporter 单元测试。"""

import io
import os

from PIL import Image

from core.controller import ExportParams, build_url, playback_durations


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


def test_playback_durations_meets_target_fps():
    """采样节奏达到目标帧率 → 均匀按目标帧率播放（每帧 1000/fps ms）。"""
    # 25fps → 目标间隔 40ms；采样间隔 40ms 均匀 10 帧
    times = [0.0 + i * 0.04 for i in range(10)]
    durs, play_fps = playback_durations(times, 25)
    assert play_fps == 25.0
    assert durs == [40] * 10
    assert sum(durs) == 400  # 播放总时长 = 真实采集时长


def test_playback_durations_slow_capture_uses_real_intervals():
    """采样节奏慢于目标帧率（整页截图太慢）→ 按真实采集间隔逐帧播放，不再补帧拖慢。"""
    # 目标 50fps，但实际每 0.5s 采一帧（整页截图慢）→ 3 帧跨 1s
    times = [0.0, 0.5, 1.0]
    durs, play_fps = playback_durations(times, 50)
    assert play_fps == 2.0  # 实际帧率 = 1/0.5
    assert durs == [500, 500, 500]  # 每帧显示真实 500ms
    assert sum(durs) == 1500  # 播放总时长 = 真实采集时长 1s（末帧多持一个间隔）


def test_playback_durations_rounds_to_centisecond():
    """GIF 帧延迟取整到 10ms（百分秒）并限幅 20~1000ms。"""
    times = [0.0, 0.133, 0.271, 0.402]  # 间隔 ~133/138/131ms
    durs, play_fps = playback_durations(times, 50)
    assert all(d % 10 == 0 for d in durs)
    assert all(20 <= d <= 1000 for d in durs)
    assert durs == [130, 140, 130, 130]
    assert abs(play_fps - round(1 / ((0.133 + 0.138 + 0.131) / 3), 3)) < 0.01


def test_playback_durations_single_frame():
    durs, play_fps = playback_durations([0.0], 25)
    assert durs == [40]
    assert play_fps == 25.0


def test_playback_durations_low_fps_under_one():
    """采集间隔非常慢（整页超大）→ 实际帧率可为小数，帧延迟限幅到上限。"""
    times = [0.0, 1.2, 2.3, 3.5]
    durs, play_fps = playback_durations(times, 60)
    assert play_fps < 1.5
    assert all(d == 1000 for d in durs)  # 每帧延迟被限幅到 1000ms 上限
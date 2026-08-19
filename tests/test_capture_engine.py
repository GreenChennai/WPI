"""capture_engine v1.3.0 行为测试：整页导出不撑爆视口高度、无限动画不阻塞。"""

import io
import time

from PIL import Image

from core.capture_engine import CaptureEngine


class _StubPage:
    def __init__(self):
        self.viewport = {"width": 800, "height": 600}
        self.set_calls = []

    def evaluate(self, _js, *_a, **_k):
        return None

    def set_viewport_size(self, size):
        self.set_calls.append(dict(size))
        self.viewport = dict(size)

    @property
    def viewport_size(self):
        return dict(self.viewport)


def _make_engine(stub=None):
    stub = stub or _StubPage()
    engine = CaptureEngine.__new__(CaptureEngine)
    engine.browser = None
    engine.page = stub
    engine.width = 800
    engine.height = 600
    return engine


def _fake_content_size(page, size):
    page.evaluate = lambda _js, *_a, **_k: list(size)


def _solid_bytes(rgb, size=(64, 64)):
    img = Image.new("RGB", size, rgb)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class _ShotPage(_StubPage):
    def __init__(self, size=(64, 64)):
        super().__init__()
        self._size = size

    def screenshot(self, **kwargs):
        return _solid_bytes((200, 200, 200), self._size)

    def evaluate(self, js, *_a, **_k):
        return None


def test_prepare_full_page_keeps_viewport_height():
    """v1.3.0：整页导出不得把视口高度撑到内容高度（else vh 样式会被撑爆）。"""
    stub = _StubPage()
    _fake_content_size(stub, [800, 2000])
    engine = _make_engine(stub)

    out_w, out_h = engine.prepare_full_page(800, None)

    assert out_w == 800
    assert out_h == 2000
    # 只设置宽度，视口高度保持原始窗口高度（600）
    assert stub.set_calls and stub.set_calls[-1]["width"] == 800
    assert stub.set_calls[-1]["height"] == 600


def test_prepare_full_page_respects_explicit_height():
    stub = _StubPage()
    _fake_content_size(stub, [800, 2000])
    engine = _make_engine(stub)

    out_w, out_h = engine.prepare_full_page(800, 900)

    assert (out_w, out_h) == (800, 2000)
    assert stub.set_calls[-1] == {"width": 800, "height": 900}


def _anim_page(finite, infinite):
    """page.evaluate 针对动画计数返回 (finite, infinite)。"""
    page = _ShotPage()
    page.evaluate = lambda js, *_a, **_k: [finite, infinite]
    return page


def test_animation_running_counts_splits_infinite():
    page = _anim_page(2, 1)
    engine = _make_engine(page)

    finite, infinite = engine.animation_running_counts()

    assert finite == 2
    assert infinite == 1
    assert engine.has_infinite_animation() is True


def test_wait_infinite_animation_finishes_immediately():
    """仅有无限循环动画时不再等待（v1.3.0 提速）。"""
    page = _anim_page(0, 3)
    engine = _make_engine(page)

    t0 = time.monotonic()
    ok = engine.wait_animation_finished(
        max_wait=60.0, sample_interval=0.01, stable_frames=2
    )
    elapsed = time.monotonic() - t0

    assert ok is True
    assert elapsed < 5.0, f"仅无限动画时不应长时间等待，实际 {elapsed:.2f}s"


def test_capture_final_frame_forwards_full_page():
    page = _ShotPage()
    engine = _make_engine(page)

    img = engine.capture_final_frame(full_page=True)

    assert img.mode == "RGBA"
    assert img.size == (64, 64)
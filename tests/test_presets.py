"""presets 纯逻辑单元测试。"""

from config.presets import (
    RATIO_PRESETS,
    SIZE_MODE_FIXED_BOTH,
    SIZE_MODE_FIXED_HEIGHT,
    SIZE_MODE_FIXED_WIDTH,
    compute_size,
    ratio_tuple,
)


def test_ratio_tuple_known():
    assert ratio_tuple("3:4") == (3, 4)
    assert ratio_tuple("1:1") == (1, 1)
    assert ratio_tuple("4:3") == (4, 3)


def test_ratio_tuple_custom():
    assert ratio_tuple("16:9") == (16, 9)
    assert ratio_tuple("bad") == (1, 1)


def test_fixed_width():
    w, h = compute_size(SIZE_MODE_FIXED_WIDTH, 1080, 0, "3:4")
    assert (w, h) == (1080, 1440)


def test_fixed_height():
    w, h = compute_size(SIZE_MODE_FIXED_HEIGHT, 0, 1440, "3:4")
    assert (w, h) == (1080, 1440)


def test_fixed_both():
    w, h = compute_size(SIZE_MODE_FIXED_BOTH, 800, 600, "1:1")
    assert (w, h) == (800, 600)


def test_ratio_consistency_roundtrip():
    for name, (rw, rh) in RATIO_PRESETS.items():
        w, h = compute_size(SIZE_MODE_FIXED_WIDTH, 2000, 0, name)
        assert w == 2000
        assert abs(w / h - rw / rh) < 0.01


def test_size_clamped():
    w, h = compute_size(SIZE_MODE_FIXED_WIDTH, 0, 0, "1:1")
    assert w >= 1 and h >= 1
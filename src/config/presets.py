"""WPI 集中配置：尺寸预设、导出默认值、版本号。

设计文档第 8 节约定，集中管理以便日后做成 GUI 可编辑项。
"""

from __future__ import annotations

import os
import sys

VERSION = "1.7.0"
APP_NAME = "Website Page to Image"
APP_TITLE = "Website Page to Image"
WORKERFILE_NAME = "WorkerFile"

# ---------------------------------------------------------------------------
# 尺寸预设（设计文档 4.3）
# ---------------------------------------------------------------------------
# 比例预设（宽, 高 的整数比）
RATIO_PRESETS: dict[str, tuple[int, int]] = {
    "3:4": (3, 4),
    "1:1": (1, 1),
    "4:3": (4, 3),
}
RATIO_PRESETS_PX: dict[str, tuple[int, int]] = {
    "3:4": (1080, 1440),
    "1:1": (1080, 1080),
    "4:3": (1080, 810),
}
FIXED_WIDTH_PRESETS: list[int] = [2000, 2400, 1080]
FIXED_HEIGHT_PRESETS: list[int] = [2000, 2400, 1080]
DEFAULT_RATIO = "1:1"

# v1.2.0：宽度预设（高度跟随网页实际内容长度）
WIDTH_PRESETS: list[int] = [2400, 1440, 1080, 800]
DEFAULT_WIDTH = 1080

# 三种尺寸约束模式
SIZE_MODE_FIXED_WIDTH = "fixed-width"
SIZE_MODE_FIXED_HEIGHT = "fixed-height"
SIZE_MODE_FIXED_BOTH = "fixed-both"
SIZE_MODES = (SIZE_MODE_FIXED_WIDTH, SIZE_MODE_FIXED_HEIGHT, SIZE_MODE_FIXED_BOTH)

SIZE_MODE_LABELS: dict[str, str] = {
    SIZE_MODE_FIXED_WIDTH: "固定宽度",
    SIZE_MODE_FIXED_HEIGHT: "固定高度",
    SIZE_MODE_FIXED_BOTH: "固定宽高",
}

DEFAULT_SIZE = (1080, 1080)

# ---------------------------------------------------------------------------
# 导出默认值（设计文档 4.5 / 8）
# ---------------------------------------------------------------------------
FORMATS = ("PNG", "GIF", "PDF")
DEFAULT_FORMAT = "PNG"
FILE_EXTENSIONS = {"PNG": ".png", "GIF": ".gif", "PDF": ".pdf"}

GIF_FPS = 15
GIF_LOOP = 0            # 0 = 无限循环
GIF_FPS_RANGE = (1, 30)
GIF_MAX_FRAMES = 240    # GIF 截取上限帧数（风险对策）

PNG_TRANSPARENT = False
PDF_PAPER = "Fit"       # 或 "A4"
FULL_PAGE_DEFAULT = True   # 固定宽/高模式导出整页内容（按页面实际尺寸）

# 预览
PREVIEW_WINDOW_SIZE = (1080, 760)

# 动画处理
ANIMATION_MAX_WAIT = 15.0      # 秒，动画"播放完毕"判定上限
ANIMATION_STABLE_FRAMES = 3    # 连续 N 帧画面不变视为动画结束
ANIMATION_SAMPLE_INTERVAL = 0.2  # 秒，动画结束轮询间隔

INDEX_FILENAMES = ("index.html", "index.htm")


def example_dir() -> str:
    """内置示例页目录（PyInstaller 单文件模式取打包内 data，开发模式取仓库 examples/）。"""
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(sys.executable)))
    else:
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, "examples", "demo")


def app_base_dir() -> str:
    """软件同级目录：打包后为 exe 所在目录，开发模式为仓库根目录。"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def app_icon_path() -> str:
    """应用图标资源路径（v1.7.0：多尺寸 ICO + PNG 兜底）。

    打包里兜底为 exe 同级 assets/，开发模式为仓库 assets/。
    返回首选 ICO；调用方可再按具体场合选用不同尺寸。
    """
    candidates = (
        "WPI_256.ico", "WPI_128.ico", "WPI_64.ico",
        "WPI_48.ico", "WPI_32.ico", "WPI.png",
    )
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", app_base_dir())
        for name in candidates:
            for base in (meipass, app_base_dir()):
                p = os.path.join(base, "assets", name)
                if os.path.isfile(p):
                    return p
    else:
        for name in candidates:
            p = os.path.join(app_base_dir(), "assets", name)
            if os.path.isfile(p):
                return p
    return ""


def app_icons_dir() -> str:
    """图标资源所在目录（assets/），供多尺寸 QIcon 组装。"""
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", app_base_dir())
        for base in (meipass, app_base_dir()):
            d = os.path.join(base, "assets")
            if os.path.isdir(d):
                return d
    return os.path.join(app_base_dir(), "assets")


def default_workspace_dir() -> str:
    """启动时自动在工作目录同级下创建 WorkerFile 作为默认工作目录。"""
    d = os.path.join(app_base_dir(), WORKERFILE_NAME)
    os.makedirs(d, exist_ok=True)
    return d


def ratio_tuple(name: str) -> tuple[int, int]:
    """按 '宽:高' 字符串返回 (w, h) 比例，找不到时回退 1:1。"""
    if name in RATIO_PRESETS:
        return RATIO_PRESETS[name]
    try:
        w, h = name.split(":")
        return (int(w), int(h))
    except (ValueError, AttributeError):
        return (1, 1)


def compute_size(
    mode: str,
    width: int,
    height: int,
    ratio_name: str = DEFAULT_RATIO,
) -> tuple[int, int]:
    """按尺寸模式计算最终导出尺寸（像素）。

    - fixed-width:  宽固定，高 = round(宽 * ratio_h / ratio_w)
    - fixed-height: 高固定，宽 = round(高 * ratio_w / ratio_h)
    - fixed-both:   宽高均固定
    """
    width = max(1, int(width))
    height = max(1, int(height))
    if mode == SIZE_MODE_FIXED_WIDTH:
        rw, rh = ratio_tuple(ratio_name)
        return (width, max(1, round(width * rh / rw)))
    if mode == SIZE_MODE_FIXED_HEIGHT:
        rw, rh = ratio_tuple(ratio_name)
        return (max(1, round(height * rw / rh)), height)
    return (width, height)

"""WPI 集中配置：尺寸预设、导出默认值、版本号。

所有预设集中管理，避免散落在各模块；日后如需做成 GUI 可编辑项，
只需在此增删即可。
"""

from __future__ import annotations

import os
import sys

VERSION = "3.0.3"
APP_NAME = "Website Page to Image"
APP_TITLE = "Website Page to Image"
WORKERFILE_NAME = "WorkerFile"

# ---------------------------------------------------------------------------
# 尺寸预设
# 尺寸语义：宽度 = 浏览器视口宽度；高度由网页实际内容长度决定。
# 因此不保留旧的"长/宽比例模式"，只约束宽度这一个变量。
# ---------------------------------------------------------------------------
WIDTH_PRESETS: list[int] = [2400, 1440, 1080, 800]
DEFAULT_WIDTH = 1080

# 分辨率倍率（原生渲染放大，非超分）：页面仍按设定宽度布局，
# 输出分辨率 × 倍率（浏览器 deviceScaleFactor），布局与比例保持不变
SCALE_PRESETS: tuple[int, ...] = (1, 2, 4, 8)
DEFAULT_SCALE = 1

# 高度锁定（默认不启用）：启用后导出内容高度锁定为该值，超出不导出、不压缩
DEFAULT_HEIGHT_LIMIT = 2560

# ---------------------------------------------------------------------------
# 导出默认值
# ---------------------------------------------------------------------------
FORMATS = ("PNG", "GIF", "MP4", "PDF")
DEFAULT_FORMAT = "PNG"
FILE_EXTENSIONS = {"PNG": ".png", "GIF": ".gif", "MP4": ".mp4", "PDF": ".pdf"}

# GIF / MP4 帧率分档：
# GIF 帧延迟以百分秒（100/FPS）为单位，必须是整数才不会出现播放器
# 无法处理的非整数延迟，故限定 10/20/25/50 四档（延迟恒为 10/5/4/2 百分秒）；
# MP4 视频编码帧率无此整数约束，按真实采样节奏编码，采用 24/30/48/60。
GIF_FPS = 25
GIF_FPS_PRESETS = (10, 20, 25, 50)
GIF_FPS_RANGE = (10, 50)
MP4_FPS = 30
MP4_FPS_PRESETS = (24, 30, 48, 60)
MP4_FPS_RANGE = (24, 60)
GIF_LOOP = 0            # 0 = 无限循环（默认开关开启）
GIF_MAX_FRAMES = 900    # GIF 截取上限帧数（最高 50fps × 15s = 750 帧，留些余量）

# 批量导出单文件看门狗超时（秒）：超过该时长后**不强制中止**（任务大 /
# 机器性能弱时属正常慢，直接退出会白白丢掉已完成部分），改为提醒 + 继续等待，
# 由用户点击「取消任务」主动停止
BATCH_ITEM_TIMEOUT_SECONDS = 900

# 渲染 rAF 节流（所有导出格式统一）：无头模式下 requestAnimationFrame 不锁
# 60fps，密集 rAF 画布动画会以数百 fps 占满渲染主线程，evaluate 续跑与
# Playwright 超时都会失效 → 导出卡死。节流到 ~30fps：大幅降低主线程负载
# 消除卡死，同时一次性 rAF 动效（墨滴扩散等逐帧动画）仍能在数秒内播完
RENDER_RAF_THROTTLE_MS = 33

# 滚动触发 reveal 遍历的步数上限：超长页面只滚前 N 步，避免遍历自身耗时过长
SCROLL_REVEAL_MAX_STEPS = 40

# 静态导出（PNG/PDF）settle 的画面稳定等待预算（秒）：打字机、墨滴扩散等
# JS 驱动的一次性动效 getAnimations() 看不到，只能靠「连续多帧整页像素不变」
# 兜底等待它们播完再截取；有无限 CSS 动画在跑时画面无法稳定，不进入该等待
ANIMATION_SETTLE_MAX_WAIT = 6.0

# 动画帧捕获加速：中间动画帧走 CDP JPEG 直采（JPEG 编码/解码远快于 PNG，
# 整页采样率可提升数倍），质量取 95 视觉无损；最终静帧（PNG/PDF）仍走 PNG 无损通道。
ANIMATION_CAPTURE_JPEG_QUALITY = 95
ANIMATION_FRAME_DURATION_MIN = 20    # ms，GIF 单帧延迟下限（2 百分秒，播放器兼容下限）
ANIMATION_FRAME_DURATION_MAX = 1000  # ms，GIF 单帧延迟上限

PNG_TRANSPARENT = False
PDF_PAPER = "Fit"       # 或 "A4"

# 预览
PREVIEW_WINDOW_SIZE = (1080, 760)

# 动画处理
ANIMATION_MAX_WAIT = 15.0      # 秒，动画"播放完毕"判定上限
ANIMATION_STABLE_FRAMES = 3    # 连续 N 帧画面不变视为动画结束
ANIMATION_SAMPLE_INTERVAL = 0.2  # 秒，动画结束轮询间隔
ANIMATION_INFINITE_WAIT = 3.0  # 秒，无限循环动画"等待完全展开"的固定时长
ASSET_WAIT = 8.0               # 秒，字体 / 图片等资源加载等待上限

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
    """应用图标资源路径。

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

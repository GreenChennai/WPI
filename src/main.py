"""WPI 入口：默认启动 PySide6 图形界面；`--export` 提供无 GUI 导出（冒烟测试用）。"""

from __future__ import annotations

import argparse
import os
import sys

from config.presets import app_icon_path, app_icons_dir


def _suppress_child_consoles() -> None:
    """Windows 打包环境下，所有子进程（Playwright 驱动、FFmpeg 等）不再弹出 CMD 窗口。

    PyInstaller `--windowed` 仅隐藏主进程自身的控制台；由本进程派生的
    node/ffmpeg 等子进程默认仍会闪出黑窗。为 Popen 补上 CREATE_NO_WINDOW，
    让 capture_output 等流水线调用也保持静默。
    """
    if os.name != "nt" or not getattr(sys, "frozen", False):
        return
    try:
        import subprocess as _sp
    except Exception:
        return
    _CREATE_NO_WINDOW = getattr(_sp, "CREATE_NO_WINDOW", 0x08000000)
    _orig_init = _sp.Popen.__init__

    def _popen_init(self, *args, **kwargs):
        flags = kwargs.get("creationflags", 0)
        kwargs["creationflags"] = (flags or 0) | _CREATE_NO_WINDOW
        return _orig_init(self, *args, **kwargs)

    if not getattr(_orig_init, "_wpi_silenced", False):
        _sp.Popen.__init__ = _popen_init
        _sp.Popen.__init__._wpi_silenced = True  # type: ignore[attr-defined]


def _build_app_icon():
    """组装多尺寸 QIcon（32/48/64/128/256 + PNG 兜底），
    让窗口 / 任务栏 / 通知区在不同 DPI 下都使用最合适的一枚。"""
    from PySide6.QtGui import QIcon, QPixmap

    icons_dir = app_icons_dir()
    icon = QIcon()
    for size in (32, 48, 64, 128, 256):
        p = os.path.join(icons_dir, f"WPI_{size}.ico")
        if os.path.isfile(p):
            icon.addPixmap(QPixmap(p))
    png = app_icon_path()
    if (not png or icon.isNull()) and png and os.path.isfile(png):
        icon.addPixmap(QPixmap(png))
    return icon


def _attach_parent_console() -> None:
    """windowed 冻结态下把输出接到父控制台，让 CLI 模式输出可见。

    PyInstaller `--windowed` 的进程没有控制台；通过 --export 从命令行调用时，
    挂到父进程（cmd/PowerShell）的控制台上以打印进度与结果。

    注意：AttachConsole 失败时**不会**抛异常（只返回 0），此时 open("CONOUT$")
    会失败而异常分支被静默吞掉，stdout 保持为 PyInstaller 用 locale 编码
    （英文系统为 cp1252）打开的重定向管道——CI 冒烟这类场景打印中文就会抛
    UnicodeEncodeError。因此无论是否附着成功，都要把 stdout/stderr 收敛成
    可写中文的 UTF-8 流。
    """
    if os.name != "nt" or not getattr(sys, "frozen", False):
        return
    try:
        import ctypes

        attached = bool(ctypes.windll.kernel32.AttachConsole(-1))
    except Exception:
        attached = False
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        if stream is None:
            # windowed 启动且没有继承到输出流：优先父控制台，否则写空设备兜底
            for target in ("CONOUT$", os.devnull):
                try:
                    stream = open(target, "w", encoding="utf-8", errors="replace")
                    break
                except Exception:
                    stream = None
            if stream is not None:
                setattr(sys, name, stream)
        elif attached:
            # 已附着父控制台：直接把输出指到控制台（utf-8），让用户看到进度
            try:
                stream = open("CONOUT$", "w", encoding="utf-8", errors="replace")
                setattr(sys, name, stream)
            except Exception:
                pass
        else:
            # 输出被重定向到管道/文件：强制 UTF-8，避免 locale 编码打印中文崩溃
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def _cmd_export(args: argparse.Namespace) -> int:
    from core.controller import ExportParams, run_export_sync

    _attach_parent_console()  # 无 GUI 导出时控制台输出可见
    fmt = (args.format or "PNG").upper()
    if fmt not in ("PNG", "GIF", "MP4", "PDF"):
        print(f"不支持的格式: {fmt}", file=sys.stderr)
        return 2
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    params = ExportParams(
        source=args.source,
        format=fmt,
        width=args.width,
        scale=args.scale,
        height=args.height,
        fps=args.fps,
        loop=args.loop,
        transparent=args.transparent,
        output_path=args.output,
        max_wait=arg_f_flag(args, "max_wait", 15.0),
        use_ffmpeg=not args.no_ffmpeg,
        full_page=not args.no_full_page,
    )
    try:
        result = run_export_sync(
            params,
            progress=lambda n: print(f"[progress] {n}%", flush=True),
            status=lambda m: print(f"[status] {m}", flush=True),
        )
    except Exception as exc:  # noqa: BLE001
        print(f"导出失败: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(f"[ok] {result}")
    return 0


def _cmd_wc_check(args: argparse.Namespace) -> int:
    """WebEngine 自检：用 QWebEngineView 加载内置示例页，验证打包内 QtWebEngine 链路（冒烟测试）。"""
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox")
    os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from config.presets import example_dir

    app = QApplication(sys.argv)
    win = None

    # 延迟导入：确保 QWebEngineProcess 在干净环境下启动
    from gui.preview_window import PreviewWindow

    win = PreviewWindow()
    state = {"ok": False}

    def _finish(ok_flag: bool):
        state["ok"] = bool(ok_flag)
        if win is not None:
            win.close()
        app.quit()

    win._view.loadFinished.connect(_finish)
    win.load(os.path.join(example_dir(), "index.html"))
    win.show()
    QTimer.singleShot(20000, app.quit)
    app.exec()
    print(f"wc-check loaded={state['ok']}")
    return 0 if state["ok"] else 1


def _cmd_selfcheck(args: argparse.Namespace) -> int:
    """使用打包内置示例页执行一次 PNG 导出，验证单文件包内数据与核心链路。"""
    import tempfile

    from config.presets import example_dir
    from core.controller import ExportParams, run_export_sync

    index = os.path.join(example_dir(), "index.html")
    if not os.path.isfile(index):
        print(f"selfcheck: 内置示例页缺失: {index}", file=sys.stderr)
        return 1
    out = os.path.join(tempfile.gettempdir(), "wpi_selfcheck.png")
    params = ExportParams(
        source=index,
        format="PNG",
        width=720,
        output_path=out,
    )
    try:
        run_export_sync(params)
    except Exception as exc:  # noqa: BLE001
        print(f"selfcheck failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(f"selfcheck OK: {out}")
    return 0


def arg_f_flag(args, name, default):
    value = getattr(args, name, None)
    return value if value is not None else default


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="WPI", description="Website Page to Image")
    parser.add_argument("--export", action="store_true", help="无 GUI 导出模式（冒烟测试）")
    parser.add_argument("--selfcheck", action="store_true", help="用内置示例页自检打包数据链路")
    parser.add_argument("--wc-check", action="store_true", help="WebEngine 打包自检（冒烟测试）")
    parser.add_argument("--source", help="源 HTML 文件或目录")
    parser.add_argument("--output", help="输出文件路径")
    parser.add_argument("--format", choices=["PNG", "GIF", "MP4", "PDF"], help="导出格式")
    parser.add_argument("--width", type=int, default=1080)
    parser.add_argument("--scale", type=int, choices=[1, 2, 4, 8], default=1,
                        help="分辨率倍率（原生渲染放大，X1/X2/X4/X8）")
    parser.add_argument("--height", type=int, default=0,
                        help="高度锁定（0=不限制；>0 内容高度锁定为该值，超出不导出）")
    parser.add_argument("--fps", type=int,
                        choices=[10, 20, 24, 25, 30, 48, 50, 60], default=25,
                        help="帧速（GIF: 10/20/25/50；MP4: 24/30/48/60）")
    parser.add_argument("--loop", type=int, default=0)
    parser.add_argument("--max-wait", type=float, dest="max_wait")
    parser.add_argument("--transparent", action="store_true")
    parser.add_argument("--no-ffmpeg", action="store_true", help="禁用 FFmpeg GIF 编码")
    parser.add_argument("--no-full-page", action="store_true",
                        help="关闭整页导出（仅按视口首屏导出）")
    return parser


def main() -> int:
    _suppress_child_consoles()
    # 确保 src/ 在 sys.path（开发模式），打包模式由 PyInstaller 处理
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)

    parser = build_parser()
    args = parser.parse_args()

    if args.export:
        if not args.source or not args.output:
            parser.error("--export 需要 --source 与 --output")
        return _cmd_export(args)

    if args.wc_check:
        return _cmd_wc_check(args)

    if args.selfcheck:
        return _cmd_selfcheck(args)

    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication

    from config.presets import APP_NAME, APP_TITLE
    from gui.style import build_stylesheet

    # QtWebEngine 沙箱兼容：单文件模式把内核解包到临时目录，--no-sandbox
    # 可避免沙箱权限不足导致渲染进程启动失败
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox")
    os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_TITLE)
    app.setWindowIcon(_build_app_icon())
    if os.name == "nt":
        app.setFont(QFont("Microsoft YaHei UI", 10))
    app.setStyleSheet(build_stylesheet())

    # 单实例锁：软件只允许打开一个实例
    from PySide6.QtCore import QLockFile, QStandardPaths

    _lock_path = os.path.join(
        QStandardPaths.writableLocation(QStandardPaths.TempLocation),
        "wpi-single-instance.lock",
    )
    _SINGLE_INSTANCE_LOCK = QLockFile(_lock_path)
    _SINGLE_INSTANCE_LOCK.setStaleLockTime(0)  # 崩溃残留锁不永久阻塞
    if not _SINGLE_INSTANCE_LOCK.tryLock(100):
        from PySide6.QtWidgets import QMessageBox

        QMessageBox.warning(None, "提示", "WPI 已在运行中，不能重复打开。")
        return 0

    from gui.main_window import MainWindow

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
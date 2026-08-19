"""WPI 入口：默认启动 PySide6 图形界面；`--export` 提供无 GUI 导出（冒烟测试用）。"""

from __future__ import annotations

import argparse
import os
import sys


def _suppress_child_consoles() -> None:
    """Windows 打包环境下，所有子进程（Playwright 驱动、FFmpeg 等）不再弹出 CMD 窗口。

    PyInstaller `--windowed` 仅隐藏主进程自身的控制台；由本进程派生的
    node/ffmpeg 等子进程默认仍会闪出黑窗。为 Popen 补上 CREATE_NO_WINDOW，
    让 capture_output 等流水线调用也保持静默（v1.4.0）。
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


def _cmd_export(args: argparse.Namespace) -> int:
    from core.controller import ExportParams, run_export_sync

    fmt = (args.format or "PNG").upper()
    if fmt not in ("PNG", "GIF", "PDF"):
        print(f"不支持的格式: {fmt}", file=sys.stderr)
        return 2
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    params = ExportParams(
        source=args.source,
        format=fmt,
        size_mode=getattr(args, "size_mode", None) or "fixed-width",
        width=args.width,
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
        height=720,
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
    parser.add_argument("--format", choices=["PNG", "GIF", "PDF"], help="导出格式")
    parser.add_argument("--width", type=int, default=1080)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--fps", type=int, default=15)
    parser.add_argument("--loop", type=int, default=0)
    parser.add_argument("--max-wait", type=float, dest="max_wait")
    parser.add_argument("--transparent", action="store_true")
    parser.add_argument("--no-ffmpeg", action="store_true", help="禁用 FFmpeg GIF 编码")
    parser.add_argument("--size-mode", choices=["fixed-width", "fixed-height", "fixed-both"],
                        help="尺寸约束模式（固定宽度/固定高度/固定宽高）")
    parser.add_argument("--no-full-page", action="store_true",
                        help="关闭整页导出（仅按视口首屏导出）")
    return parser


def main() -> int:
    _suppress_child_consoles()   # v1.4.0：子进程不弹 CMD 窗口
    if True:  # 确保 src/ 在 sys.path（开发模式），打包模式由 PyInstaller 处理
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
    from PySide6.QtGui import QFont, QIcon
    from PySide6.QtWidgets import QApplication

    from config.presets import APP_NAME, APP_TITLE, app_icon_path
    from gui.style import build_stylesheet

    # QtWebEngine 沙箱兼容（单文件解包到临时目录时避免提权失败）
    if True:
        os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox")
        os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_TITLE)
    icon_path = app_icon_path()
    if icon_path:
        app.setWindowIcon(QIcon(icon_path))
    if os.name == "nt":
        app.setFont(QFont("Microsoft YaHei UI", 10))
    app.setStyleSheet(build_stylesheet())

    from gui.main_window import MainWindow

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
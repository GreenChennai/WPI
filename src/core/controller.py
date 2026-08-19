"""任务编排（Controller）：加载 → 渲染 → 捕获 → 编码 → 写出。

- 既可作为 PySide6 工作线程的 QObject Worker（带信号），
  也可被 CLI `--export` / 冒烟测试以同步方式调用（run_export_sync）。
"""

from __future__ import annotations

import os
import urllib.parse
from dataclasses import dataclass, field


@dataclass
class ExportParams:
    source: str                     # HTML 文件路径 或 目录
    format: str = "PNG"             # PNG / GIF / PDF
    size_mode: str = "fixed-width"  # 尺寸约束模式（用于整页导出定向）
    width: int = 1080
    height: int = 1080
    fps: int = 15
    loop: int = 0
    transparent: bool = False
    output_path: str = ""
    max_wait: float = 15.0
    use_ffmpeg: bool = True
    full_page: bool = True          # PNG/PDF：按页面实际内容长度导出
    extra_warnings: list[str] = field(default_factory=list)


def build_url(source: str, server) -> str:
    """由源路径解析出挂载目录 + 访问 URL。"""
    if os.path.isfile(source):
        directory = os.path.dirname(os.path.abspath(source))
        url = server.base_url + "/" + urllib.parse.quote(os.path.basename(source))
    else:
        directory = os.path.abspath(source)
        from core.static_server import resolve_index

        index = resolve_index(directory)
        if index:
            url = server.base_url + "/" + index
        else:
            raise FileNotFoundError(f"所选目录中未找到任何 HTML 文件: {directory}")
        server.directory = directory
    return url


def run_export_sync(params: ExportParams, progress=None, status=None) -> dict:
    from core.browser_host import BrowserHost
    from core.capture_engine import CaptureEngine
    from core.static_server import StaticServer
    from export.gif_exporter import GIFExporter
    from export.pdf_exporter import PDFExporter
    from export.png_exporter import PNGExporter

    if not params.output_path:
        raise ValueError("未指定输出路径")

    def _status(msg: str) -> None:
        if status is not None:
            status(msg)

    def _progress(n: int) -> None:
        if progress is not None:
            progress(n)

    server: StaticServer | None = None
    browser: BrowserHost | None = None
    warnings: list[str] = list(params.extra_warnings)

    try:
        _status("启动本地静态服务…")
        server = StaticServer(params.source if os.path.isdir(params.source)
                              else os.path.dirname(os.path.abspath(params.source)))
        server.start()
        url = build_url(params.source, server)
        _progress(8)

        _status("启动系统浏览器内核…")
        browser = BrowserHost()
        browser.launch()
        _progress(25)

        _status("渲染页面…")
        engine = CaptureEngine.load(browser, url, (params.width, params.height))
        warnings.extend(engine.collect_resource_warnings())
        _progress(40)

        result: dict = {
            "format": params.format,
            "path": params.output_path,
            "width": params.width,
            "height": params.height,
            "warnings": warnings,
            "frames": 1,
        }

        if params.format == "GIF":
            if params.full_page:
                _status("按网页实际内容高度调整视口…")
                width, height = engine.prepare_full_page(params.width, None)
                _progress(45)
            _status("录制动画帧…")

            def _on_frame(n: int) -> None:
                _progress(min(80, 45 + n))

            frames, times = engine.capture_frames(
                fps=params.fps,
                max_wait=params.max_wait,
                full_page=params.full_page,
                on_frame=_on_frame,
            )
            durations = []
            for i in range(len(times)):
                if i + 1 < len(times):
                    d = int(round((times[i + 1] - times[i]) * 1000))
                else:
                    d = durations[-1] if durations else int(round(1000 / params.fps))
                durations.append(d)
            _status("编码 GIF…")
            gif = GIFExporter().write(
                frames, params.output_path,
                fps=params.fps, loop=params.loop,
                durations=durations,
                use_ffmpeg=params.use_ffmpeg,
            )
            fw, fh = frames[0].size
            result["width"] = width if params.full_page else fw
            result["height"] = height if params.full_page else fh
            result["frames"] = gif["frames"]
            result["encoder"] = gif["encoder"]
            result["duration_ms"] = sum(durations)
            result["full_page"] = params.full_page
            _progress(98)

        elif params.format == "PNG":
            # v1.7.0：PNG 直接导出页面当前（正常）状态，不等待动画播放
            if params.full_page:
                _status("测量并导出整页内容…")
                actual_w, _actual_h = engine.prepare_full_page(params.width, None)
                image = engine.capture_final_frame(
                    transparent=params.transparent, full_page=True
                )
                result["width"] = actual_w
                result["height"] = image.size[1]
                result["full_page"] = True
            else:
                image = engine.capture_final_frame(transparent=params.transparent)
            _status("编码 PNG…")
            PNGExporter.write(image, params.output_path, transparent=params.transparent)
            result["warnings"] = warnings
            _progress(98)

        else:  # PDF
            # v1.7.0：PDF 直接打印页面当前（正常）状态，不等待动画播放
            out_w, out_h = params.width, params.height
            if params.full_page:
                _status("测量并打印整页内容…")
                out_w, out_h = engine.prepare_full_page(params.width, None)
                result["width"] = out_w
                result["height"] = out_h
                result["full_page"] = True
            else:
                result["width"] = out_w
                result["height"] = out_h
            _status("打印为 PDF…")
            PDFExporter.write(engine.page, params.output_path, out_w, out_h)
            result["warnings"] = warnings
            _progress(98)

        result["warnings"] = warnings
        _progress(100)
        return result

    finally:
        if browser is not None:
            browser.close()
        if server is not None:
            server.stop()


try:  # GUI 场景才依赖 PySide6；CLI/冒烟测试可脱离 GUI 运行
    from PySide6.QtCore import QObject, Signal  # type: ignore

    class Controller(QObject):
        progress = Signal(int)
        status = Signal(str)
        result = Signal(object)
        failed = Signal(str)

        def __init__(self, parent=None):
            super().__init__(parent)
            self._params: ExportParams | None = None

        def set_params(self, params: ExportParams) -> None:
            self._params = params

        def run(self) -> None:
            params = self._params
            if params is None:
                self.failed.emit("导出参数为空")
                return
            try:
                res = run_export_sync(
                    params,
                    progress=lambda n: self.progress.emit(n),
                    status=lambda m: self.status.emit(m),
                )
                self.result.emit(res)
            except Exception as exc:  # noqa: BLE001
                try:
                    import traceback

                    traceback.print_exc()
                except Exception:
                    pass
                self.failed.emit(str(exc))

except ImportError:  # PySide6 缺失时仅提供同步入口
    pass
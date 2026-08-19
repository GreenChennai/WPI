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
    width: int = 1080
    fps: int = 15
    loop: int = 0
    transparent: bool = False
    output_path: str = ""
    max_wait: float = 15.0
    use_ffmpeg: bool = True
    full_page: bool = True          # PNG/PDF：整页导出（高度随网页实际内容长度）
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
    from export.mp4_exporter import MP4Exporter
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
        is_url = isinstance(params.source, str) and params.source.startswith(
            ("http://", "https://")
        )
        if is_url:
            # v2.0.0：在线网站直接以 URL 加载，无需本地静态服务
            url = params.source
            _status("连接在线网站…")
        else:
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
        engine = CaptureEngine.load(browser, url, (params.width, params.width))
        warnings.extend(engine.collect_resource_warnings())
        _progress(40)

        # v1.8.0：导出前确保内容已完整呈现（字体 / 图片加载 + 动画收敛到终态），
        # 避免截到未渲染的纯色块。GIF 仍需录制动画过程，只等静态资源即可。
        if params.format == "GIF":
            engine.wait_assets()
        else:
            engine.settle()
        _progress(45)

        result: dict = {
            "format": params.format,
            "path": params.output_path,
            "width": params.width,
            "height": params.width,
            "warnings": warnings,
            "frames": 1,
        }

        if params.format == "GIF":
            # v2.0.0：滚动逐帧录制整页（触发 reveal-on-scroll 入场动画并覆盖
            # 全部内容），解决「只录到顶部标题、下方是背景色块」的问题。
            _status("滚动录制整页动画帧…")

            def _on_frame(n: int) -> None:
                _progress(min(85, 45 + n))

            frames, times = engine.capture_scroll_frames(
                fps=params.fps,
                max_wait=params.max_wait,
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
            result["width"] = fw
            result["height"] = fh
            result["frames"] = gif["frames"]
            result["encoder"] = gif["encoder"]
            result["duration_ms"] = sum(durations)
            _progress(98)

        elif params.format == "MP4":
            # v2.0.0：与 GIF 共用滚动录制，再用 FFmpeg 编码为 H.264 MP4
            _status("滚动录制整页动画帧…")

            def _on_frame(n: int) -> None:
                _progress(min(85, 45 + n))

            frames, times = engine.capture_scroll_frames(
                fps=params.fps,
                max_wait=params.max_wait,
                on_frame=_on_frame,
            )
            _status("编码 MP4…")
            mp4 = MP4Exporter().write(
                frames, params.output_path,
                fps=params.fps, use_ffmpeg=params.use_ffmpeg,
            )
            fw, fh = frames[0].size
            result["width"] = fw
            result["height"] = fh
            result["frames"] = len(frames)
            result["encoder"] = mp4["encoder"]
            result["duration_ms"] = int(round((times[-1] - times[0]) * 1000)) if len(times) > 1 else 0
            _progress(98)

        elif params.format == "PNG":
            # v1.8.0：导出前已 settle（等待资源加载 + 动画收敛到终态），
            # 此处直接截取完整呈现后的页面当前状态。
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

        elif params.format == "PDF":
            # v1.8.0：导出前已 settle，此处直接打印完整呈现后的页面当前状态。
            out_w, out_h = params.width, params.width
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


def _unique_path(path: str) -> str:
    """目标文件已存在时追加 _1/_2... 数字后缀，避免覆盖同名文件（v2.0.0）。"""
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    i = 1
    while True:
        cand = f"{base}_{i}{ext}"
        if not os.path.exists(cand):
            return cand
        i += 1


def run_batch_sync(
    params_list: list[ExportParams],
    progress=None,
    status=None,
) -> dict:
    """批量导出：依次导出 params_list 中的每一项（v1.9.0 多选批量导出）。

    任一文件失败即停止并向上抛出（遇错停止、成功继续，由调用方回报）。
    重名文件自动追加数字后缀，不覆盖（v2.0.0）。
    返回 {"batch": True, "results": [...], "count": N}。
    """
    total = len(params_list)
    results: list[dict] = []
    for i, params in enumerate(params_list):
        stem = os.path.basename(params.source)
        if status is not None:
            status(f"导出 {i + 1}/{total}: {stem}")
        params.output_path = _unique_path(params.output_path)
        res = run_export_sync(
            params,
            progress=(
                lambda n: progress(int((i + n / 100.0) / total * 100))
                if progress is not None else None
            ),
            status=status,
        )
        results.append(res)
    return {"batch": True, "results": results, "count": total}


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
            self._params_list: list[ExportParams] | None = None
            self._batch: bool = False

        def set_params(self, params: ExportParams) -> None:
            self._params = params
            self._batch = False

        def set_params_list(self, params_list: list[ExportParams]) -> None:
            self._params_list = params_list
            self._batch = True

        def run(self) -> None:
            if self._batch:
                if not self._params_list:
                    self.failed.emit("批量导出参数为空")
                    return
                try:
                    res = run_batch_sync(
                        self._params_list,
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
                return
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
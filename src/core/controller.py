"""任务编排（Controller）：加载 → 渲染 → 捕获 → 编码 → 写出。

- 既可作为 PySide6 工作线程的 QObject Worker（带信号），
  也可被 CLI `--export` / 冒烟测试以同步方式调用（run_export_sync）。
"""

from __future__ import annotations

import os
import urllib.parse
from dataclasses import dataclass, field

from config.presets import GIF_MAX_FRAMES


@dataclass
class ExportParams:
    source: str                     # HTML 文件路径 / 目录 / http(s):// URL
    format: str = "PNG"             # PNG / GIF / MP4 / PDF
    width: int = 1080
    scale: int = 1                  # 分辨率倍率（原生渲染，X1/X2/X4/X8）
    height: int = 0                 # 高度锁定（0=不限制；>0 内容高度锁定，超出不导出）
    fps: int = 15
    loop: int = 0
    transparent: bool = False
    output_path: str = ""
    max_wait: float = 15.0
    use_ffmpeg: bool = True
    full_page: bool = True          # PNG/PDF：整页导出（高度随网页实际内容长度）
    extra_warnings: list[str] = field(default_factory=list)


def playback_durations(times: list[float], fps: int) -> tuple[list[int], float]:
    """按实际采集时刻计算每帧播放时长(ms)与实际播放帧率。

    核心目标：GIF / MP4 播放速度恒等于真实时间，绝不用帧重复把动画拖慢。

    - 采集节奏达到目标帧率（平均采集间隔 ≤ 目标间隔×1.05，允许轻微抖动）时：
      按目标帧率均匀播放，返回每帧 1000/fps 毫秒。
    - 采集节奏慢于目标帧率（整页截图耗时超过 1/fps，采样率上不去）时：
      按真实采集间隔逐帧播放——每帧显示时长 = 它到下一帧的真实间隔（GIF 取整到
      10ms=百分秒并限幅 20~1000ms），不再把少量采样帧重复撑到 fps×时长。

    返回 (每帧时长ms列表, 实际播放帧率)。列表长度与 frames/times 一致。
    """
    from config.presets import (
        ANIMATION_FRAME_DURATION_MAX,
        ANIMATION_FRAME_DURATION_MIN,
    )

    target_fps = max(1, int(fps))
    n = len(times)
    if n <= 1:
        d = round(1000.0 / target_fps)
        return [d] * n, float(target_fps)
    intervals = [times[i + 1] - times[i] for i in range(n - 1)]
    avg = sum(intervals) / len(intervals)
    target_iv = 1.0 / target_fps
    if avg <= target_iv * 1.05:
        d = max(ANIMATION_FRAME_DURATION_MIN, round(1000.0 / target_fps))
        return [d] * n, float(target_fps)
    last = intervals[-1] if intervals else avg
    durs = []
    for iv in intervals + [last]:
        ms = int(round(iv * 1000.0 / 10.0) * 10)
        ms = max(ANIMATION_FRAME_DURATION_MIN,
                 min(ANIMATION_FRAME_DURATION_MAX, ms))
        durs.append(ms)
    return durs, round(1.0 / avg, 3)


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
            # 在线网站直接以 URL 加载，无需本地静态服务
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
        engine = CaptureEngine.load(
            browser, url, (params.width, params.width), device_scale=params.scale
        )
        warnings.extend(engine.collect_resource_warnings())
        _progress(40)

        # 导出前确保内容已完整呈现（字体 / 图片加载 + 动画收敛到终态），
        # 避免截到未渲染的纯色块。GIF/MP4 需录制动画过程：等资源 + 滚动触发
        # reveal 内容展开（不冻结动画）；PNG/PDF 则 settle 收敛到终态。
        if params.format in ("GIF", "MP4"):
            engine.wait_assets()
            engine.trigger_scroll_reveals()   # 整页可见，reveal 内容已展开
        else:
            engine.settle()
        _progress(45)

        # 高度锁定：视口高度设为锁定值（浏览器窗口能呈现的最高高度），
        # 内容不压缩，超出部分不导出
        if params.height and params.height > 0:
            _status("设置锁定高度视口…")
            engine.page.set_viewport_size(
                {"width": params.width, "height": int(params.height)}
            )
            engine.page.wait_for_timeout(150)

        result: dict = {
            "format": params.format,
            "path": params.output_path,
            "width": params.width,
            "height": params.width,
            "warnings": warnings,
            "frames": 1,
        }

        if params.format == "GIF":
            # 与 PNG 尺寸语义一致——只限制宽度，高度为网页自然内容高度（整页逐帧）；
            # 高度锁定时只录制顶部锁定区域。
            # 录满 max_wait 时长（真实时间采样），按真实采集节奏计算每帧延迟，
            # 播放速度恒等于真实时间，不用重复帧把动画拖慢。
            _status("录制整页动画帧…")

            def _on_frame(n: int) -> None:
                _progress(min(85, 45 + n))

            frames, times = engine.capture_frames(
                fps=params.fps,
                max_wait=params.max_wait,
                max_frames=GIF_MAX_FRAMES,
                early_stop=False,
                full_page=not (params.height > 0),
                on_frame=_on_frame,
            )
            durations, play_fps = playback_durations(times, params.fps)
            _status("编码 GIF…")
            gif = GIFExporter().write(
                frames, params.output_path,
                fps=play_fps, loop=params.loop,
                durations=durations,
                use_ffmpeg=params.use_ffmpeg,
            )
            fw, fh = frames[0].size
            result["width"] = fw
            result["height"] = fh
            result["frames"] = gif["frames"]
            result["encoder"] = gif["encoder"]
            result["play_fps"] = play_fps
            result["duration_ms"] = sum(durations)
            _progress(98)

        elif params.format == "MP4":
            # 与 GIF 共用整页逐帧录制，FFmpeg 高保真编码（x264 crf0）。
            # 逐帧 JPEG 加速采样 + 按真实采样节奏编码——采样率达不到设定帧率时
            # 按实际帧率编码（播放速度 = 真实时间，不拖慢）；达到时按设定帧率
            # 编码（帧数足、时长正确）。
            _status("录制整页动画帧…")

            def _on_frame(n: int) -> None:
                _progress(min(85, 45 + n))

            frames, times = engine.capture_frames(
                fps=params.fps,
                max_wait=params.max_wait,
                early_stop=False,          # 录满 max_wait 时长
                full_page=not (params.height > 0),
                on_frame=_on_frame,
            )
            _durations, play_fps = playback_durations(times, params.fps)
            _status("编码 MP4…")
            mp4 = MP4Exporter().write(
                frames, params.output_path,
                fps=play_fps, use_ffmpeg=params.use_ffmpeg,
            )
            fw, fh = frames[0].size
            result["width"] = fw
            result["height"] = fh
            result["frames"] = len(frames)
            result["encoder"] = mp4["encoder"]
            result["play_fps"] = play_fps
            result["duration_ms"] = int(
                len(frames) * 1000.0 / max(play_fps, 1e-3)
            )
            _progress(98)

        elif params.format == "PNG":
            # 导出前已 settle（等待资源加载 + 动画收敛到终态），
            # 此处直接截取完整呈现后的页面当前状态。
            if params.height and params.height > 0:
                # 高度锁定：只导出顶部锁定高度范围内的内容
                _status("按锁定高度导出…")
                image = engine.capture_highres(
                    height_css=int(params.height),
                    transparent=params.transparent,
                    scale=params.scale,
                )
                result["width"] = image.size[0]
                result["height"] = image.size[1]
                result["height_locked"] = True
            elif params.full_page:
                _status("测量并导出整页内容…")
                actual_w, _actual_h = engine.prepare_full_page(params.width, None)
                # 高倍率（4X/8X）下 captureBeyondViewport 单拍受 Chromium 最大
                # 截图尺寸限制会截断组件 → 改分块滚动截图 + 拼接；capture_highres
                # 内部对未超上限的页面仍单拍优先
                if params.scale > 2:
                    image = engine.capture_highres(
                        transparent=params.transparent, scale=params.scale
                    )
                else:
                    image = engine.capture_final_frame(
                        transparent=params.transparent, full_page=True
                    )
                result["width"] = image.size[0]
                result["height"] = image.size[1]
                result["full_page"] = True
            else:
                image = engine.capture_final_frame(transparent=params.transparent)
                result["width"] = image.size[0]
                result["height"] = image.size[1]
            _status("编码 PNG…")
            PNGExporter.write(image, params.output_path, transparent=params.transparent)
            result["warnings"] = warnings
            _progress(98)

        elif params.format == "PDF":
            # 导出前已 settle，此处直接打印完整呈现后的页面当前状态。
            out_w, out_h = params.width, params.width
            if params.height and params.height > 0:
                # 高度锁定：打印高度锁定为该值
                out_h = int(params.height)
                result["width"] = out_w
                result["height"] = out_h
                result["height_locked"] = True
            elif params.full_page:
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
    """目标文件已存在时追加 _1/_2... 数字后缀，避免覆盖同名文件。"""
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
    """批量导出：依次导出 params_list 中的每一项。

    任一文件失败即停止并向上抛出（遇错停止、成功继续，由调用方回报）。
    重名文件自动追加数字后缀，不覆盖。
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
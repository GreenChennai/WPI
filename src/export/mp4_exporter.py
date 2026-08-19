"""MP4 导出：把滚动录制的帧序列用 FFmpeg 编码为 H.264 MP4（v2.0.0）。

帧序列由 CaptureEngine.capture_scroll_frames 提供（与 GIF 同源）。
FFmpeg 发现顺序同 GIFExporter：WPI_FFMPEG 环境变量 → 软件同目录 → PATH。
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile

from PIL import Image

from export.gif_exporter import (
    _hide_console_flags,
    app_dir,
    find_ffmpeg,
)


class MP4Exporter:
    def __init__(self, ffmpeg: str | None = None):
        self.ffmpeg = ffmpeg or find_ffmpeg((app_dir(),))

    def write(self, frames: list[Image.Image], path: str, fps: int = 15,
              use_ffmpeg: bool = True) -> dict:
        """把帧序列编码为 H.264 / yuv420p / faststart 的 MP4。

        需要 FFmpeg（含 libx264）。无 FFmpeg 时直接抛错，由调用方回报用户。
        """
        if not (use_ffmpeg and self.ffmpeg):
            raise RuntimeError("MP4 导出需要 FFmpeg（未找到或未启用）")
        frames = [f.convert("RGB") for f in frames]
        out = os.path.abspath(path)
        os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="wpi_mp4_") as td:
            for i, frame in enumerate(frames, start=1):
                frame.save(os.path.join(td, f"frame_{i:05d}.png"))
            cmd = [
                self.ffmpeg, "-y", "-loglevel", "error",
                "-framerate", str(max(1, int(fps))),
                "-i", os.path.join(td, "frame_%05d.png"),
                "-vf", "format=yuv420p",
                "-movflags", "+faststart",
                "-c:v", "libx264",
                out,
            ]
            subprocess.run(
                cmd, check=True, capture_output=True,
                creationflags=_hide_console_flags(),
            )
        return {"encoder": "FFmpeg", "frames": len(frames)}

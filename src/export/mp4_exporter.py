"""MP4 导出：把整页逐帧序列用 FFmpeg 编码为 H.264 **高保真** MP4。

帧序列由 CaptureEngine.capture_frames(full_page=True) 提供（与 GIF 同源）。
逐帧采样默认走 CDP JPEG（质量 95，视觉无损）以换取更高采样率（动画更流畅），
故称"高保真"而非位级无损；H.264 编码仍为 x264 crf 0 + yuv444p。
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

    def write(self, frames: list[Image.Image], path: str, fps: float = 30,
              use_ffmpeg: bool = True) -> dict:
        """把帧序列编码为 H.264 **高保真** MP4（帧源走 JPEG 加速采样）。

        libx264 `-crf 0` + `-pix_fmt yuv444p` 为无损编码（High 4:4:4），
        帧像素零损失、体积较大属正常；帧源为 CDP JPEG（质量 95，视觉无损），
        适合二次剪辑后处理。fps 可为小数（采样率不足时按真实采样节奏编码，
        保证播放速度 = 真实时间）。需要 FFmpeg（含 libx264）。
        无 FFmpeg 时直接抛错，由调用方回报用户。
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
                "-framerate", str(round(float(fps), 3)),
                "-i", os.path.join(td, "frame_%05d.png"),
                "-c:v", "libx264",
                "-crf", "0",           # 无损
                "-preset", "slow",
                "-pix_fmt", "yuv444p", # 无 4:2:0 色度抽稀，真无损
                "-movflags", "+faststart",
                out,
            ]
            subprocess.run(
                cmd, check=True, capture_output=True,
                creationflags=_hide_console_flags(),
            )
        return {"encoder": "FFmpeg(高保真)", "frames": len(frames)}

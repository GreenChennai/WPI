"""GIF 导出：优先 FFmpeg 调色板优化，无 FFmpeg 时回退 Pillow。

FFmpeg 发现顺序：WPI_FFMPEG 环境变量 → 软件同目录 → PATH。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

from PIL import Image


def app_dir() -> str:
    """可执行程序所在目录（PyInstaller 单文件模式取 exe 目录）。"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def find_ffmpeg(extra_dirs: tuple[str, ...] = ()) -> str | None:
    env = os.environ.get("WPI_FFMPEG")
    if env and os.path.isfile(env):
        return env
    for d in extra_dirs or ():
        for cand in (os.path.join(d, "ffmpeg.exe"), os.path.join(d, "bin", "ffmpeg.exe")):
            if os.path.isfile(cand):
                return cand
    found = shutil.which("ffmpeg")
    return found


class GIFExporter:
    def __init__(self, ffmpeg: str | None = None):
        self.ffmpeg = ffmpeg or find_ffmpeg((app_dir(),))

    def write(
        self,
        frames: list[Image.Image],
        path: str,
        fps: int = 15,
        loop: int = 0,
        durations: list[int] | None = None,
        use_ffmpeg: bool = True,
    ) -> dict:
        frames = [f.convert("RGBA") for f in frames]
        used = "Pillow"
        if use_ffmpeg and self.ffmpeg:
            try:
                self._write_ffmpeg(frames, path, fps, loop)
                used = "FFmpeg"
            except Exception:
                used = "Pillow(fallback)"
                self._write_pillow(frames, path, fps, loop, durations)
        else:
            self._write_pillow(frames, path, fps, loop, durations)
        return {"encoder": used, "frames": len(frames)}

    @staticmethod
    def _write_pillow(
        frames: list[Image.Image],
        path: str,
        fps: int,
        loop: int,
        durations: list[int] | None = None,
    ) -> None:
        duration_ms = round(1000 / max(1, int(fps)))
        if durations:
            # 按实际采集间隔设置每帧时长，保证 GIF 播放速度贴近真实时间
            #（上限 1000ms、下限 20ms=2 百分秒，播放器兼容）
            duration_ms = [max(20, min(1000, d)) for d in durations]
        imgs = [f.convert("P", palette=Image.ADAPTIVE, colors=256) for f in frames]
        imgs[0].save(
            path,
            format="GIF",
            save_all=True,
            append_images=imgs[1:],
            duration=duration_ms,
            loop=loop,
            disposal=2,
        )

    @staticmethod
    def _write_ffmpeg(frames: list[Image.Image], path: str, fps: float, loop: int) -> None:
        with tempfile.TemporaryDirectory(prefix="wpi_gif_") as td:
            for i, frame in enumerate(frames, start=1):
                rgba = frame.convert("RGBA")
                bg = Image.new("RGB", rgba.size, (255, 255, 255))
                bg.paste(rgba, mask=rgba.getchannel("A"))
                bg.save(os.path.join(td, f"frame_{i:05d}.png"))
            cmd = [
                find_ffmpeg(), "-y", "-loglevel", "error",
                "-framerate", str(round(float(fps), 3)),  # 支持小数实际帧率
                "-i", os.path.join(td, "frame_%05d.png"),
                "-filter_complex",
                "[0:v]split[x][y];[x]palettegen=stats_mode=diff[p];"
                "[y][p]paletteuse=dither=sierra2_4a",
                "-loop", str(loop),
                path,
            ]
            subprocess.run(
                cmd, check=True, capture_output=True,
                creationflags=_hide_console_flags(),
            )


def _hide_console_flags() -> int:
    """Windows 下禁止子进程弹出 CMD 控制台窗口。"""
    if os.name == "nt":
        return getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return 0

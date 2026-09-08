"""WPI-noGUI-cli 入口:无 GUI 纯命令行导出器。

与 GUI 版共用同一条渲染/捕获/编码链路(Playwright + 系统 Edge/Chrome +
Pillow + 可选 FFmpeg),不导入任何 PySide6/Qt 模块——GUI 专属代码
(src/gui)与界面资源一律不进包。打包规格见 tools/wpi-cli.spec。

FFmpeg 不随附本程序:运行时按 WPI_FFMPEG 环境变量 → 同级目录 → PATH
发现;GIF 在无 FFmpeg 时自动回退 Pillow 编码,MP4 必须环境提供 FFmpeg。
"""

from __future__ import annotations

import argparse
import os
import sys

from config.presets import VERSION
from main import _cmd_export, _cmd_selfcheck, _suppress_child_consoles


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="WPI-noGUI-cli",
        description=(
            "Website Page to Image 无 GUI 命令行导出器:"
            "把本地网页项目或在线网站渲染导出为 PNG / GIF / MP4 / PDF"
        ),
    )
    parser.add_argument(
        "--version", action="version",
        version=f"WPI-noGUI-cli {VERSION}",
    )
    parser.add_argument("--source", help="源 HTML 文件、项目目录或 http(s):// URL")
    parser.add_argument("--output", help="输出文件路径(扩展名随 --format)")
    parser.add_argument("--format", choices=["PNG", "GIF", "MP4", "PDF"],
                        default="PNG", help="导出格式(默认 PNG)")
    parser.add_argument("--width", type=int, default=1080,
                        help="浏览器视口宽度 px(默认 1080,高度随内容)")
    parser.add_argument("--scale", type=int, choices=[1, 2, 4, 8], default=1,
                        help="分辨率倍率(原生渲染放大,默认 X1)")
    parser.add_argument("--height", type=int, default=0,
                        help="高度锁定 px(0=不限制;>0 超出部分不导出)")
    parser.add_argument("--fps", type=int,
                        choices=[10, 20, 24, 25, 30, 48, 50, 60], default=25,
                        help="帧速(GIF: 10/20/25/50;MP4: 24/30/48/60)")
    parser.add_argument("--loop", type=int, default=0,
                        help="GIF 循环次数(0=无限循环)")
    parser.add_argument("--max-wait", type=float, dest="max_wait", default=15.0,
                        help="动画录制/等待时长上限秒(默认 15)")
    parser.add_argument("--transparent", action="store_true",
                        help="PNG 保留透明背景")
    parser.add_argument("--no-ffmpeg", action="store_true",
                        help="禁用 FFmpeg(GIF 回退 Pillow 编码)")
    parser.add_argument("--no-full-page", action="store_true",
                        help="关闭整页导出(仅按视口首屏)")
    parser.add_argument("--selfcheck", action="store_true",
                        help="用内置示例页执行一次 PNG 导出自检,校验部署环境")
    return parser


def main() -> int:
    _suppress_child_consoles()   # Playwright/FFmpeg 子进程不闪 CMD 窗口
    # 确保 src/ 在 sys.path(开发模式直跑 python src/cli.py);打包模式由
    # PyInstaller 把 cli.py 设为入口,import main 同样成立
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)

    parser = build_parser()
    args = parser.parse_args()

    if args.selfcheck:
        return _cmd_selfcheck(args)
    if not args.source or not args.output:
        parser.error("需要 --source 与 --output(或使用 --selfcheck 自检)")
    return _cmd_export(args)


if __name__ == "__main__":
    sys.exit(main())

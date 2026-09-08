"""WPI 构建脚本（UTF-8 安全）：PyInstaller 单文件打包 + 离线冒烟。

一次构建产出两个单文件 exe（+ 随附 ffmpeg.exe + 文档）：
- WPI-GUI.exe        完整图形界面版（PySide6 + QtWebEngine，windowed）
- WPI-noGUI-cli.exe  无 GUI 纯命令行导出器（剔除 PySide6，console）

用法:
    python tools/build.py [--out 目录] [--version 版本号] [--no-smoke]

版本号默认 `{semver}-{short_hash}`（git 可用取 7 位哈希，否则用时间戳）。
"""

from __future__ import annotations

import argparse
import datetime
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(ROOT, "src")
DEMO_DIR = os.path.join(ROOT, "examples", "demo")
DEFAULT_OUT_BASE = r"E:\平日资料\构建"
SEMVER = "3.2.0"

# PySide6 仅实际使用 QtWidgets/QtGui/QtCore/QtNetwork + QtWebEngine 链路。
# 其余 Qt 模块（多媒体/3D/图表/位置/PDF/虚拟键盘等）排除逻辑已内置于
# tools/wpi.spec（excludes + Qt DLL 白名单瘦身），build.py 不再重复维护。
# 无 GUI 版 tools/wpi-cli.spec 整包剔除 PySide6，产出 WPI-noGUI-cli.exe。

GUI_EXE_NAME = "WPI-GUI.exe"
CLI_EXE_NAME = "WPI-noGUI-cli.exe"


def resolve_version(custom: str | None) -> str:
    if custom:
        return custom
    hash_ = None
    try:
        out = subprocess.run(
            ["git", "-C", ROOT, "rev-parse", "--short=7", "HEAD"],
            capture_output=True, text=True, timeout=10, check=False,
        )
        if out.returncode == 0 and out.stdout.strip():
            hash_ = out.stdout.strip()
    except Exception:
        hash_ = None
    if not hash_:
        hash_ = datetime.datetime.now().strftime("%Y%m%d%H%M")
    return f"{SEMVER}-{hash_}"


def clean_dirs() -> None:
    for name in ("build", "dist"):
        path = os.path.join(ROOT, name)
        if os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)


def _find_ffmpeg_src() -> str | None:
    """在常见构建目录中找一个可用的 ffmpeg.exe（供 GIF/MP4 编码打包）。"""
    candidates = [os.path.join(ROOT, "tools", "ffmpeg.exe")]
    # ROOT = E:\平日资料\GitHub\WPI → 上级的上级 = E:\平日资料 → 构建目录
    parent = os.path.dirname(os.path.dirname(ROOT))
    build_base = os.path.join(parent, "构建")
    candidates.append(os.path.join(build_base, "MomentShift-v0.9.0", "ffmpeg.exe"))
    # 也扫描 构建 目录下较新的构建（MomentShift / WPI 各版本）
    try:
        if os.path.isdir(build_base):
            for name in sorted(os.listdir(build_base), reverse=True):
                p = os.path.join(build_base, name, "ffmpeg.exe")
                if os.path.isfile(p):
                    candidates.append(p)
    except Exception:
        pass
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


def _run_pyinstaller(spec_path: str, dist_dir: str, exe_name: str, build_root: str) -> str:
    """跑一次 PyInstaller 单文件构建,把产物移入 build_root,返回其路径。"""
    stub = os.path.join(build_root, "_stub")
    os.makedirs(stub, exist_ok=True)
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--distpath", stub,
        "--workpath", os.path.join(ROOT, "build"),
        spec_path,
    ]
    subprocess.run(cmd, check=True)
    exe = os.path.join(stub, exe_name)
    if not os.path.isfile(exe):
        raise FileNotFoundError(f"PyInstaller 未产出: {exe}")
    target = os.path.join(build_root, exe_name)
    shutil.move(exe, target)
    shutil.rmtree(stub, ignore_errors=True)
    return target


def build_gui_exe(build_root: str) -> str:
    """图形界面版:tools/wpi.spec(exclude + Qt DLL 白名单瘦身)。"""
    return _run_pyinstaller(
        os.path.join(ROOT, "tools", "wpi.spec"), build_root, GUI_EXE_NAME, build_root
    )


def build_cli_exe(build_root: str) -> str:
    """无 GUI 命令行版:tools/wpi-cli.spec(整包剔除 PySide6)。

    不随附 ffmpeg.exe——编码算法保留在包内,运行时按 WPI_FFMPEG /
    同级目录 / PATH 发现;无 FFmpeg 时 GIF 回退 Pillow,MP4 明确报错。
    """
    return _run_pyinstaller(
        os.path.join(ROOT, "tools", "wpi-cli.spec"), build_root, CLI_EXE_NAME, build_root
    )


def write_metadata(build_root: str, version: str) -> None:
    shutil.copy2(os.path.join(ROOT, "README.md"), build_root)
    cli_readme = os.path.join(ROOT, "README-CLI.md")
    if os.path.isfile(cli_readme):
        shutil.copy2(cli_readme, build_root)
    with open(os.path.join(build_root, "VERSION.txt"), "w", encoding="utf-8") as fh:
        fh.write(
            f"WPI {version}\n"
            "WPI-GUI.exe:      GUI 版 (PySide6 + Playwright + Pillow + 随附 ffmpeg)\n"
            "WPI-noGUI-cli.exe: 无 GUI 命令行版 (Playwright + Pillow, 不随附 ffmpeg)\n"
            "renderer: system Edge/Chrome (no bundled browser)\n"
        )


def _run_export_smoke(exe: str, out: str, extra: list[str]) -> None:
    cmd = [exe, "--source", DEMO_DIR, "--output", out, *extra]
    proc = subprocess.run(
        cmd, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=300, check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"smoke {' '.join(extra) or 'default'} failed rc={proc.returncode}"
            f"\n{proc.stdout}\n{proc.stderr}")
    if not os.path.isfile(out) or os.path.getsize(out) == 0:
        raise RuntimeError(f"smoke produced empty file: {out}")


def smoke_test(build_root: str, gui_exe: str, cli_exe: str) -> None:
    print("== offline smoke: GUI ==")
    cases = (
        ("smoke.png", ["--export", "--format", "PNG", "--width", "1080"]),
        ("smoke_x2.png", ["--export", "--format", "PNG", "--width", "1080", "--scale", "2"]),
        ("smoke.gif", ["--export", "--format", "GIF", "--width", "1080", "--fps", "10"]),
        ("smoke.mp4", ["--export", "--format", "MP4", "--width", "1080", "--fps", "10"]),
        ("smoke.pdf", ["--export", "--format", "PDF", "--width", "1080"]),
    )
    for name, extra in cases:
        out = os.path.join(build_root, name)
        _run_export_smoke(gui_exe, out, extra)
        print(f"smoke {name} OK ({os.path.getsize(out)} bytes)")
        os.remove(out)

    # WebEngine 打包链路自检（离线，验证内置 QtWebEngine 可用）。
    # QtWebEngine 首次启动偶发 GPU 子进程竞争 → 自动重试一次。
    for attempt in (1, 2):
        proc = subprocess.run(
            [gui_exe, "--wc-check"], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=120, check=False,
        )
        if proc.returncode == 0:
            break
        print(f"smoke wc-check attempt {attempt} failed rc={proc.returncode}, retrying…")
    else:
        raise RuntimeError(
            f"smoke wc-check failed rc={proc.returncode}\n{proc.stdout}\n{proc.stderr}")
    print("smoke wc-check OK")

    print("== offline smoke: noGUI CLI ==")
    # CLI 与 GUI 共用同一导出链路,抽 PNG / GIF / PDF 三种格式 + --selfcheck
    # (内置示例页自检)验证打包数据;CLI 版不附带 ffmpeg,此处与其同级目录
    # 恰有随 GUI 版附带的 ffmpeg.exe,正好覆盖「发现 FFmpeg 则用之」的路径。
    cli_cases = (
        ("smoke_cli.png", ["--format", "PNG", "--width", "1080"]),
        ("smoke_cli.gif", ["--format", "GIF", "--width", "1080", "--fps", "10"]),
        ("smoke_cli.pdf", ["--format", "PDF", "--width", "1080"]),
    )
    for name, extra in cli_cases:
        out = os.path.join(build_root, name)
        _run_export_smoke(cli_exe, out, extra)
        print(f"smoke {name} OK ({os.path.getsize(out)} bytes)")
        os.remove(out)
    proc = subprocess.run(
        [cli_exe, "--selfcheck"], capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=300, check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"smoke cli --selfcheck failed rc={proc.returncode}\n{proc.stdout}\n{proc.stderr}")
    print("smoke cli --selfcheck OK")


def main() -> int:
    parser = argparse.ArgumentParser(description="WPI build (PyInstaller onefile)")
    parser.add_argument("--out", default=DEFAULT_OUT_BASE, help="build archive root")
    parser.add_argument("--version", default=None, help="override version")
    parser.add_argument("--no-smoke", action="store_true", help="skip offline smoke")
    args = parser.parse_args()

    version = resolve_version(args.version)
    build_root = os.path.join(args.out, f"WPI-v{version}")
    os.makedirs(build_root, exist_ok=True)
    print(f"build target: {build_root}")

    clean_dirs()
    gui_exe = build_gui_exe(build_root)
    cli_exe = build_cli_exe(build_root)
    # 随包附带 ffmpeg（GUI 版 GIF 调色板 / MP4 编码需要），放在 exe 同级目录，
    # 运行时由 export.gif_exporter.find_ffmpeg 经 app_dir() 自动发现;
    # noGUI CLI 版不打包 ffmpeg,但同目录恰有此文件时也会按发现顺序利用。
    ff = _find_ffmpeg_src()
    if ff:
        shutil.copy2(ff, os.path.join(build_root, "ffmpeg.exe"))
        print(f"bundled ffmpeg: {ff}")
    else:
        print("WARNING: 未找到 ffmpeg，GIF/MP4 编码可能回退或失败")
    write_metadata(build_root, version)
    if not args.no_smoke:
        smoke_test(build_root, gui_exe, cli_exe)
    clean_dirs()

    print("=" * 46)
    print(f"done: {os.path.join(build_root, GUI_EXE_NAME)}")
    print(f"      {os.path.join(build_root, CLI_EXE_NAME)}")
    print(f"version: {version}")
    print("=" * 46)
    return 0


if __name__ == "__main__":
    sys.exit(main())

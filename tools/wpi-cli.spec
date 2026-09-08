# -*- mode: python ; coding: utf-8 -*-
"""WPI-noGUI-cli PyInstaller spec:无 GUI 纯命令行导出器(单文件 + console)。

与 GUI 版(tools/wpi.spec)的差异:
- 入口 src/cli.py:只走 core/export/config 链路,不导入任何 PySide6 模块
  (controller 的 QObject Worker 由 try/except ImportError 自动降级为同步入口);
- 整包剔除 PySide6/Qt:体积从 ~210 MB 降到 ~40 MB,无 WebEngine/Qt DLL;
- 不打入界面资源(图标 PNG/ICO 资产、下拉箭头、示例外的任何 data);
  仅保留 examples/demo 供 --selfcheck 自检;
- console=True:命令行运行时进度/结果直接输出到控制台。

用法:由 tools/build.py 驱动(与 GUI 版同一构建流程产出双 exe)。
"""

import os

# ROOT = spec 所在目录的上一级（即仓库根）。PyInstaller 在 spec 命名空间
# 提供 SPEC（spec 的绝对路径）与 SPECPATH（其所在目录）。
ROOT = os.path.dirname(SPECPATH)
SRC_DIR = os.path.join(ROOT, "src")
DEMO_DIR = os.path.join(ROOT, "examples", "demo")
ASSETS_DIR = os.path.join(ROOT, "assets")
ICON_ICO = os.path.join(ASSETS_DIR, "WPI_256.ico")   # exe 资源图标(仅外壳,无运行时依赖)

a = Analysis(
    [os.path.join(SRC_DIR, "cli.py")],
    pathex=[SRC_DIR],
    binaries=[(DEMO_DIR, "examples/demo")],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # 无 GUI 版整包剔除 PySide6:顶层名排除即覆盖全部子模块;explicit
    # 列出常用子模块仅为在构建日志中显式可见,防止未来有人把 import 加回
    excludes=[
        "PySide6",
        "PySide6.QtCore", "PySide6.QtGui", "PySide6.QtWidgets",
        "PySide6.QtNetwork", "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets", "PySide6.QtSvg",
        "gui", "gui.main_window", "gui.workspace_panel",
        "gui.preview_window", "gui.style", "gui.tokens",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="WPI-noGUI-cli",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,          # CLI 生命线:进度/结果/报错直接进控制台
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON_ICO,
)

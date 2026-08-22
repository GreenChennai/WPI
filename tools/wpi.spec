# -*- mode: python ; coding: utf-8 -*-
"""WPI PyInstaller spec：单文件 + windowed + 定向瘦身。

PySide6 hook 通过 collect_all 会把全部 100+ 个 Qt DLL 打入包内，
--exclude-module 无法拦截 DLL。此 spec 在 Analysis 之后按过滤规则
剔除未使用的 Qt 子系统 DLL 与 devtools 调试资源，显著减小体积。

用法：由 tools/build.py 以 --specpath 方式驱动的 spec 构建。
"""

import os
import re

# ROOT = spec 所在目录的上一级（即仓库根）。PyInstaller 在 spec 命名空间
# 提供 SPEC（spec 的绝对路径）与 SPECPATH（其所在目录）。
ROOT = os.path.dirname(SPECPATH)
SRC_DIR = os.path.join(ROOT, "src")
DEMO_DIR = os.path.join(ROOT, "examples", "demo")
ASSETS_DIR = os.path.join(ROOT, "assets")
ICON_ICO = os.path.join(ASSETS_DIR, "WPI_256.ico")   # EXE 图标（多尺寸 ICO 全家桶）
ICON_PNG = os.path.join(ASSETS_DIR, "WPI.png")

# 全部尺寸图标一并打入包内，运行时按 DPI 选择最合适的一枚
_ICON_SIZES = ("32", "48", "64", "128", "256")
_ICON_DATAS = [(os.path.join(ASSETS_DIR, "WPI.png"), "assets")]
_ICON_DATAS += [
    (os.path.join(ASSETS_DIR, f"WPI_{s}.ico"), "assets") for s in _ICON_SIZES
]
# 「+」按钮图标（加号.svg），打入包内 assets，保证 exe 内正常显示
_ICON_DATAS += [(os.path.join(ASSETS_DIR, "加号.svg"), "assets")]

# 下拉箭头 PNG 资源（src/gui/assets → 包内 gui/assets，供 QSS image:url() 引用）
_GUI_ASSETS_DIR = os.path.join(SRC_DIR, "gui", "assets")
_ICON_DATAS += [(_GUI_ASSETS_DIR, "gui/assets")]

block_cipher = None

# ---------------------------------------------------------------------------
# 需要保留的 Qt 运行时依赖（依据 dumpbin /dependents 分析出的
# QtWebEngineWidgets 链路，见上方注释块）。除下列外其余 Qt6*.dll 全部剔除；
# 同时剔除 QtMultimedia 附带的 FFmpeg 动态库。
# ---------------------------------------------------------------------------
_KEEP_DLL = {
    "PySide6\\Qt6Core.dll",
    "PySide6\\Qt6Gui.dll",
    "PySide6\\Qt6Widgets.dll",
    "PySide6\\Qt6Network.dll",
    "PySide6\\Qt6OpenGL.dll",
    "PySide6\\Qt6PrintSupport.dll",
    "PySide6\\Qt6Qml.dll",
    "PySide6\\Qt6QmlCore.dll",
    "PySide6\\Qt6QmlCompiler.dll",
    "PySide6\\Qt6QmlLocalStorage.dll",
    "PySide6\\Qt6QmlMeta.dll",
    "PySide6\\Qt6QmlModels.dll",
    "PySide6\\Qt6QmlNetwork.dll",
    "PySide6\\Qt6QmlWorkerScript.dll",
    "PySide6\\Qt6QmlXmlListModel.dll",
    "PySide6\\Qt6Quick.dll",
    "PySide6\\Qt6QuickWidgets.dll",
    "PySide6\\Qt6Svg.dll",
    "PySide6\\Qt6Sql.dll",
    "PySide6\\Qt6Concurrent.dll",
    "PySide6\\Qt6Positioning.dll",
    "PySide6\\Qt6WebChannel.dll",
    "PySide6\\Qt6WebEngineCore.dll",
    "PySide6\\Qt6WebEngineWidgets.dll",
    "PySide6\\Qt6WebEngineProcess.exe",
    "PySide6\\qtwebengine_process.exe",   # 部分发行版小写命名
}


def _drop_binary(name: str) -> bool:
    """非白名单的 PySide6 子模块 DLL/EXE 一律剔除；非 PySide6 文件保留。"""
    norm = name.replace("/", "\\")
    # webengine 调试专用资源（.debug.pak / .debug.bin，体积大且 release 不需要）
    if ".debug.pak" in norm or "v8_context_snapshot.debug.bin" in norm:
        return True
    if not norm.startswith("PySide6\\"):
        return False
    # QtWebEngine 渲染进程与 FFmpeg 动态库：FFmpeg 来自 QtMultimedia，不使用
    if "Qt6WebEngineProcess" in norm or norm.lower().endswith("qtwebengine_process.exe"):
        return False  # 保留渲染进程
    if norm in _KEEP_DLL:
        return False
    # 剔除其余 Qt6 DLL
    if norm.startswith("PySide6\\Qt6"):
        return True
    # 剔除 FFmpeg 附库（avcodec/avformat/avutil/swresample/swscale）
    base = os.path.basename(norm).lower()
    for prefix in ("avcodec-", "avformat-", "avutil-", "swresample-", "swscale-"):
        if base.startswith(prefix):
            return True
    # 剔除 PySide6 自带的设计器/QML 工具 exe（不用）
    tools = {
        "assistant.exe", "balsam.exe", "balsamui.exe", "designer.exe",
        "linguist.exe", "lrelease.exe", "lupdate.exe", "qmlcachegen.exe",
        "qmlformat.exe", "qmlimportscanner.exe", "qmllint.exe", "qmlls.exe",
        "qmltyperegistrar.exe", "qsb.exe", "rcc.exe", "svgtoqml.exe", "uic.exe",
        "Qt6WebEngineQuickDelegatesQml.dll", "Qt6WebEngineQuick.dll",
        "Qt6QuickControls2.dll",
    }
    if base in tools:
        return True
    return False


def _drop_data(name: str) -> bool:
    """剔除 webengine 调试专用资源：
    - 所有 .debug.pak / v8_context_snapshot.debug.bin（体积大，release 不需要）
    - devtools 资源包（仅供 F12/远程调试，本软件不用）
    保留 qtwebengine_resources*.pak 与 locales，保证渲染进程正常初始化。"""
    n = name.replace("/", "\\")
    if ".debug.pak" in n or "v8_context_snapshot.debug.bin" in n:
        return True
    return "qtwebengine_devtools_resources.pak" in n


a = Analysis(
    [os.path.join(SRC_DIR, "main.py")],
    pathex=[SRC_DIR],
    binaries=[(DEMO_DIR, "examples/demo")],
    datas=_ICON_DATAS,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "PySide6.Qt3DAnimation", "PySide6.Qt3DCore", "PySide6.Qt3DExtras",
        "PySide6.Qt3DInput", "PySide6.Qt3DLogic", "PySide6.Qt3DRender",
        "PySide6.QtAxContainer", "PySide6.QtBluetooth", "PySide6.QtCanvasPainter",
        "PySide6.QtCharts", "PySide6.QtDataVisualization", "PySide6.QtDesigner",
        "PySide6.QtGraphs", "PySide6.QtGraphsWidgets", "PySide6.QtHelp",
        "PySide6.QtHttpServer", "PySide6.QtLocation", "PySide6.QtLottie",
        "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets",
        "PySide6.QtNetworkAuth", "PySide6.QtNfc", "PySide6.QtPdf",
        "PySide6.QtPdfWidgets", "PySide6.QtRemoteObjects", "PySide6.QtScxml",
        "PySide6.QtSensors", "PySide6.QtSerialBus", "PySide6.QtSerialPort",
        "PySide6.QtSpatialAudio", "PySide6.QtStateMachine", "PySide6.QtTest",
        "PySide6.QtTextToSpeech", "PySide6.QtUiTools",
        "PySide6.QtVirtualKeyboard", "PySide6.QtWebSockets", "PySide6.QtWebView",
        "PySide6.QtXml",
        "PySide6.QtQuick3D", "PySide6.QtQuick3DAssetImport",
        "PySide6.QtQuick3DAssetUtils", "PySide6.QtQuick3DEffects",
        "PySide6.QtQuick3DGlslParser", "PySide6.QtQuick3DHelpers",
        "PySide6.QtQuick3DHelpersImpl", "PySide6.QtQuick3DIblBaker",
        "PySide6.QtQuick3DParticleEffects", "PySide6.QtQuick3DParticles",
        "PySide6.QtQuick3DRuntimeRender", "PySide6.QtQuick3DSpatialAudio",
        "PySide6.QtQuick3DUtils", "PySide6.QtQuick3DXr",
        "PySide6.QtQuickTimeline", "PySide6.QtQuickTest",
    ],
    noarchive=False,
)

a.binaries = [(k, v, typecode) for k, v, typecode in a.binaries if not _drop_binary(k)]
a.datas = [(k, v, typecode) for k, v, typecode in a.datas if not _drop_data(k)]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="WPI",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON_ICO,
)
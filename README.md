<p align="center">
  <img src="assets/WPI.png" width="160" alt="WPI logo">
</p>

<h1 align="center">Website Page to Image (WPI)</h1>

<p align="center">桌面端工具：将本地前端网页（HTML + CSS + JS）或在线网站按指定宽度渲染，导出为 <b>PNG / GIF / MP4 / PDF</b>，内置交互式预览窗口。</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/UI-PySide6-41CD52" alt="PySide6">
  <img src="https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-4FC08D" alt="Platform">
  <img src="https://img.shields.io/badge/License-MIT-yellow" alt="License">
</p>

---

## 功能特性

- **网页渲染导出**：以本地 `index.html` 作为项目入口，自动挂载静态服务，将页面完整渲染后导出为 **PNG / GIF / MP4 / PDF**；也支持输入在线网站 URL 直接导出。
- **交互式预览**：内置预览窗口实时预览（可点击 / 滚动），也可在系统浏览器中打开（支持 F12 审查元素）。
- **尺寸语义清晰**：`宽度 = 浏览器视口宽度`，`高度 = 网页实际内容长度`；提供 2400 / 1440 / 1080 / 800 预设，支持自定义宽度与 X1/X2/X4/X8 原生分辨率倍率。
- **动画渲染**：GIF / MP4 录制整页动画，播放速度恒等于真实时间；PNG / PDF 导出前自动等待资源加载、触发 reveal-on-scroll 展开并冻结有限动画，确保截到完整呈现后的内容。
- **PDF 输出**：按屏幕样式打印（所见即所得），超长内容自动分页为常规尺寸，Edge / Chrome 均可正常查看。
- **批量导出与多选**：`Shift` 连选 / `Ctrl` 单选批量勾选项目，一键批量导出；重名文件自动追加 `_1 / _2…` 后缀，绝不覆盖。
- **工作目录卡片流**：项目以彩色卡片展示并自动提取网站主色色卡，支持进入子目录继续浏览。
- **命令行导出**：`WPI.exe --export` 支持无 GUI 纯命令行导出。
- **设置记忆**：工作目录、导出宽度、输出路径自动持久化，重启后恢复。

## 快速开始

### 环境要求

- Python 3.11+
- 已安装 **Microsoft Edge** 或 **Google Chrome**（本工具通过 Playwright 系统通道调用，不内置浏览器）
- **FFmpeg**：打包版已随附 `ffmpeg.exe`（位于 WPI.exe 同目录）；源码运行时可自行安装或通过 `WPI_FFMPEG` 环境变量指定。GIF 优先使用 FFmpeg 调色板优化（缺失时回退 Pillow），**MP4 必须使用 FFmpeg**。

### 安装依赖

```bash
pip install PySide6 playwright Pillow pyinstaller pytest
```

### 运行 GUI

```bash
python src\main.py
```

首次启动会在软件目录自动创建 `WorkerFile` 工作目录，放入含 `index.html` 的网页项目文件夹即可识别。

### 无 GUI 导出（命令行）

```bash
python src\main.py --export --source examples\demo --output out.png --format PNG --width 1080
python src\main.py --export --source examples\demo --output out.gif --format GIF --width 1080 --fps 15
python src\main.py --export --source examples\demo --output out.mp4 --format MP4 --width 1080 --fps 30
python src\main.py --export --source examples\demo --output out.pdf --format PDF --width 1080
python src\main.py --export --source https://example.com --output out.png --format PNG --width 1440
```

打包后的 `WPI.exe` 同样支持：`WPI.exe --export --source <路径或URL> --output out.png --format PNG --width 1080`（自动挂接控制台输出）。

## 使用流程

1. **选择工作目录**：点击「更换目录…」或使用默认的 `WorkerFile`。
2. **选择项目**：点击左侧项目卡片；卡片显示项目名、主色调色卡与操作按钮。支持 `Ctrl` 单选、`Shift` 连选进行批量勾选（多选时「预览当前项目」不可用，但可「批量导出」）。
3. **预览确认**：点击「预览」在内置窗口查看页面；「浏览器打开」可在系统浏览器中 F12 审查元素。
4. **设置尺寸**：输入或选择导出宽度（高度跟随网页内容自动计算）；需要更高清输出时在「分辨率倍率」选 X2 / X4 / X8（布局不变、分辨率原生放大）。如需导出在线网站，在「在线网站」地址框输入 URL，可先点「预览」或「浏览器打开」确认。
5. **导出**：选择输出路径与格式，点击「导出」（多选时按钮变为「批量导出 (N)」）即可获取文件；多文件导出时以输出路径所在目录为目标，每个 HTML 单独成文件，重名自动加 `_1/_2…` 后缀。

## 构建打包

本地构建（构建 + 离线冒烟测试 + 归档）：

```bash
python tools\build.py            # 构建 + 离线冒烟测试 + 归档
```

产出于 `工具所在盘\构建\WPI-v{version}\WPI.exe`（单文件可执行程序，含内置示例页与图标，体积约 200 MB 且已剔除未使用的 Qt 子系统）。

GitHub 推送到 `main` 分支时，由 GitHub Actions 自动构建并发布 Release（含附 ffmpeg 的 ZIP 与单文件 exe）。

## 目录结构

```
WPI/
├── assets/                  # 应用图标（WPI.png + 多尺寸 WPI_*.ico）
├── src/
│   ├── main.py              # 入口（GUI + --export CLI + --wc-check 自检）
│   ├── gui/                 # 表示层：主窗口 / 工作目录 / 尺寸 / 导出 / 预览 / 主题
│   ├── core/                # 控制层：controller / browser_host / capture_engine / static_server
│   ├── export/              # 编码链路：png / gif / mp4 / pdf exporter
│   └── config/              # presets（预设、版本号）/ settings（配置持久化）
├── examples/demo/           # 内置示例页（含 CSS/JS/图片/动画）
├── tools/                   # build.py 构建脚本 + wpi.spec 打包配置
├── pyproject.toml
└── README.md
```

## 测试

测试文件仅保留在开发者本地（`tests/` 已从仓库排除），不随仓库同步。

```bash
python -m pytest tests -q
```

## 注意事项

- 浏览器内核缺失时程序会明确提示，请安装 Edge 或 Chrome。
- 外部链接资源加载失败会在导出完成后提醒（页面仍正常导出）。
- 无限动画受「时长上限」与「帧数上限」约束（默认 15s / 900 帧）。
- 打包后的单文件程序启动时需解压，首次启动稍慢属正常现象。

## License

[MIT](LICENSE)

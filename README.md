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

- **网页渲染导出**：以本地 `index.html` 作为项目入口，自动挂载静态服务，将页面完整渲染后导出。
- **多入口 HTML 选择**：项目内存在多个 HTML（如 `index.html` / `index2.html` / `index3.html`）时，项目卡片提供入口下拉框，可切换要预览 / 导出 / 浏览器打开的页面。
- **四种输出格式**：
  - **PNG** — 整页高清截图，支持透明背景；导出前自动等待字体 / 图片加载完成，并把有限动画收敛到终态（如渐显、位移入场），确保截到的是完整呈现后的内容，不再出现未渲染的纯色块。
  - **GIF** — 整页逐帧录制动画（转场、轮播、Hover 等），只限制宽度、高度为网页自然内容高度（与 PNG 一致），可选帧率与循环次数。
  - **MP4** — 与 GIF 同一套整页帧序列，FFmpeg 编码为 **H.264 无损视频**（crf 0 + yuv444p，随包附送 ffmpeg），体积较大，适合二次剪辑后处理。
  - **PDF** — 整页排版输出，按**屏幕样式**渲染（所见即所得，避免网页打印样式导致全白）；导出前完成资源加载与动画收敛。
- **在线网站导出**：导出尺寸下方新增「在线网站」地址框，输入 URL 后可一键「预览」、在系统浏览器中打开，或直接导出（支持 PNG / GIF / MP4 / PDF 全部格式），与本地项目流程完全一致。
- **动画渲染**：GIF / MP4 录制前先触发 reveal-on-scroll 内容展开（整页可见，不冻结动画）；PNG / PDF 在导出前等待字体 / 图片就绪并将有限动画锁定为「播放完毕」状态，无限循环动画则等待其完全展开（默认 3s）后再截取。
- **批量导出与多选**：在工作目录卡片上 `Shift` 连选（从锚点到目标）、`Ctrl` 单选可批量勾选多个项目；选中集合自动排入队列，点击「导出」一次性批量导出。单选时卡片为绿色（#E8F5E9 / #1F883D），≥2 个时整体切换为蓝色（#E3F0FF / #0969DA）以区分。批量导出遇到重名文件自动追加 `_1 / _2…` 数字后缀，绝不覆盖。
- **多 HTML 项目一键导出全部**：项目内包含多个 HTML 时，卡片在下拉框前提供「导出全部 HTML」勾选，勾选后批量导出该项目内的每一个 HTML 文件。
- **滚动触发动画处理**：PNG / PDF 导出前除了等待资源与冻结有限动画，还会主动滚动遍历整页以触发 reveal-on-scroll 入场动画（IntersectionObserver / 滚动监听），确保整页截图截到的是完全展开后的内容。
- **工作目录卡片流**：工作目录下的每个项目以彩色卡片展示，自动提取网站主色生成色卡，双击进入二级 / 三级子目录继续浏览，支持返回上级；空目录下居中显示放大的「无可用项目」提示。
- **交互式预览**：内置预览窗口直接调用渲染内核，无需浏览器即可实时预览；也可在系统浏览器中打开静态服务地址（支持 F12 审查元素）。
- **尺寸语义清晰**：`宽度 = 浏览器视口宽度`，`高度 = 网页实际内容长度`（软件仅受宽度约束，导出即按内容实际长度）；提供 2400 / 1440 / 1080 / 800 预设，支持任意自定义宽度。
- **高度锁定**：导出尺寸下「高度」行默认不启用，勾选后（默认 2560）导出内容高度锁定为该值——相当于浏览器窗口能呈现的最高高度，超出部分不导出、内容不压缩。
- **分辨率倍率（原生放大）**：「导出尺寸」下新增 X1 / X2 / X4 / X8 分辨率倍率下拉。页面仍按设定宽度布局（比例与排布完全不变），但导出分辨率按倍率原生放大——底层使用浏览器的 `deviceScaleFactor` 高 DPI 渲染（如 1080px × X2 = 2160px 宽输出），是真实矢量级高清，而非超分插值。4X / 8X 整页导出采用「滚动触发栅格化 + 视口相对 clip 分块」拼接（v2.3.0 重做）：每块恒为视口大小、clip 由浏览器按倍率自动缩放，无手工像素裁切，杜绝接缝 / 模糊 / 组件错位。
- **单端口静态服务**：预览与「浏览器打开」共用进程内唯一的本地静态服务（整个软件只占一个端口）；在「工作目录」中切换项目时只需切换该服务的挂载目录，URL 自动带唯一参数并禁用缓存，保证切换后一定加载新项目，不再为每个预览/打开新开端口。
- **GIF / MP4 参数**：帧率下拉可选 15 / 24 / 30 / 48 / 60 fps；「无限循环」开关默认勾选（垂直左对齐），取消勾选后才显示次数输入窗口（最小 1）；所有数字输入框已去除 +/- 步进按钮，界面更清爽。
- **下拉箭头**：使用指定图标资源（chevron 朝下箭头），普通下拉框与项目卡片入口下拉框统一显示。
- **无 GUI 导出（命令行）**：`WPI.exe --export` 支持纯命令行导出本地项目或在线网站，无需打开界面。
- **单实例运行**：软件只允许打开一个实例，重复启动会提示「WPI 已在运行中」。
- **设置记忆**：工作目录、导出宽度、输出路径等配置自动持久化到 `WPI_settings.json`，重启后自动恢复。
- **启动提速**：界面骨架先行，QtWebEngine / Playwright 按需延迟加载。

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

```bash
python tools\build.py            # 构建 + 离线冒烟测试 + 归档
```

产出于 `工具所在盘\构建\WPI-v{version}\WPI.exe`（单文件可执行程序，含内置示例页与图标，体积约 200 MB 且已剔除未使用的 Qt 子系统）。

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
├── tests/                   # 单元 / 集成测试（无需 GUI）
├── tools/                   # build.py 构建脚本 + wpi.spec 打包配置
├── pyproject.toml
└── README.md
```

## 测试

```bash
python -m pytest tests -q
```

## 注意事项

- 浏览器内核缺失时程序会明确提示，请安装 Edge 或 Chrome。
- 外部链接资源加载失败会在导出完成后提醒（页面仍正常导出）。
- 无限动画受「时长上限」与「帧数上限」约束（默认 15s / 240 帧）。
- 打包后的单文件程序启动时需解压，首次启动稍慢属正常现象。

## License

[MIT](LICENSE)

<p align="center">
  <img src="assets/WPI.png" width="160" alt="WPI logo">
</p>

<h1 align="center">Website Page to Image (WPI)</h1>

<p align="center">桌面端工具：将本地前端网页（HTML + CSS + JS）按指定宽度渲染，导出为 <b>PNG / GIF / PDF</b>，内置交互式预览窗口。</p>

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
- **三种输出格式**：
  - **PNG** — 整页高清截图，支持透明背景；导出前自动等待字体 / 图片加载完成，并把有限动画收敛到终态（如渐显、位移入场），确保截到的是完整呈现后的内容，不再出现未渲染的纯色块。
  - **GIF** — 逐帧录制页面动画（含转场、轮播、Hover），可选帧率。
  - **PDF** — 整页排版输出，适合存档与打印；同样在导出前完成资源加载与动画收敛。
- **动画渲染**：GIF 完整播放页面动画并逐帧录制；PNG / PDF 在导出前等待字体 / 图片就绪并将有限动画锁定为「播放完毕」状态，无限循环动画则等待其完全展开（默认 3s）后再截取。
- **批量导出与多选**：在工作目录卡片上 `Shift` 连选（从锚点到目标）、`Ctrl` 单选可批量勾选多个项目；选中集合自动排入队列，点击「导出」一次性批量导出。单选时卡片为绿色（#E8F5E9 / #1F883D），≥2 个时整体切换为蓝色（#E3F0FF / #0969DA）以区分。
- **多 HTML 项目一键导出全部**：项目内包含多个 HTML 时，卡片在下拉框前提供「导出全部 HTML」勾选，勾选后批量导出该项目内的每一个 HTML 文件。
- **滚动触发动画处理**：PNG / PDF 导出前除了等待资源与冻结有限动画，还会主动滚动遍历整页以触发 reveal-on-scroll 入场动画（IntersectionObserver / 滚动监听），确保整页截图截到的是完全展开后的内容。
- **工作目录卡片流**：工作目录下的每个项目以彩色卡片展示，自动提取网站主色生成色卡，双击进入二级 / 三级子目录继续浏览，支持返回上级；空目录下提示文案在面板内居中显示。
- **交互式预览**：内置预览窗口直接调用渲染内核，无需浏览器即可实时预览；也可在系统浏览器中打开静态服务地址（支持 F12 审查元素）。
- **尺寸语义清晰**：`宽度 = 浏览器视口宽度`，`高度 = 网页实际内容长度`（软件仅受宽度约束，导出即按内容实际长度）；提供 2400 / 1440 / 1080 / 800 预设，支持任意自定义宽度。
- **设置记忆**：工作目录、导出宽度、输出路径等配置自动持久化到 `WPI_settings.json`，重启后自动恢复。
- **启动提速**：界面骨架先行，QtWebEngine / Playwright 按需延迟加载。

## 快速开始

### 环境要求

- Python 3.11+
- 已安装 **Microsoft Edge** 或 **Google Chrome**（本工具通过 Playwright 系统通道调用，不内置浏览器）
- （可选）**FFmpeg** 用于 GIF 调色板优化；未安装时自动回退 Pillow 编码。可通过 `WPI_FFMPEG` 环境变量或把 `ffmpeg.exe` 放到软件执行文件同目录指定。

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
python src\main.py --export --source examples\demo --output out.pdf --format PDF --width 1080
```

## 使用流程

1. **选择工作目录**：点击「更换目录…」或使用默认的 `WorkerFile`。
2. **选择项目**：点击左侧项目卡片；卡片显示项目名、主色调色卡与操作按钮。支持 `Ctrl` 单选、`Shift` 连选进行批量勾选（多选时「预览当前项目」不可用，但可「批量导出」）。
3. **预览确认**：点击「预览」在内置窗口查看页面；「浏览器打开」可在系统浏览器中 F12 审查元素。
4. **设置尺寸**：输入或选择导出宽度（高度跟随网页内容自动计算）。
5. **导出**：选择输出路径与格式，点击「导出」（多选时按钮变为「批量导出 (N)」）即可获取文件；多文件导出时以输出路径所在目录为目标，每个 HTML 单独成文件。

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
│   ├── export/              # 编码链路：png / gif / pdf exporter
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

---

## 更新日志

### v1.9.0
- **批量导出与多选**：工作目录卡片支持 `Ctrl` 单选、`Shift` 连选批量勾选；选中集合排入队列，点击「导出」一次性批量导出（按钮在多选时变为「批量导出 (N)」）。单选卡片为绿色（#E8F5E9 / #1F883D），≥2 个时整体切换为蓝色（#E3F0FF / #0969DA）。多选时「预览当前项目」不可用。
- **多 HTML 一键导出全部**：项目内含多个 HTML 时，卡片在下拉框前提供「导出全部 HTML」勾选，勾选后批量导出该项目内每一个 HTML 文件。
- **空状态提示居中**：工作目录为空时的提示文案在「工作目录」组件内纵向 + 横向居中显示。
- **移除整页导出复选框与长宽尺寸死代码**：「整页导出（高度按网页实际内容长度）」勾选无意义（高度本就跟随内容），已移除；同时清理 `RATIO_PRESETS` / `SIZE_MODE_*` / `compute_size` / `ratio_tuple` 等旧尺寸约束模式的无用代码，软件导出现仅受宽度约束。
- **滚动触发动画处理**：PNG / PDF 导出前 `settle()` 新增「滚动遍历整页」步骤，主动触发 reveal-on-scroll 入场动画（IntersectionObserver / 滚动监听），确保整页截图截到完全展开后的内容。
- **构建**：归档于 `构建\WPI-v1.9.0\`。

### v1.8.0
- **导出内容完整呈现**：PNG / PDF 导出前新增 `settle()` 流程——等待 Web 字体与主资源（含懒加载图片）加载完成，并将有限时长动画 `finish()` 收敛到终态，无限循环动画等待其完全展开（默认 3s）后再截取，彻底解决「截到未渲染纯色块」的问题。
- **预览窗口尺寸修正**：窗口高度固定 850；宽度按用户在尺寸面板设定的网页宽度精确贴合（加载后测量并校正，左右无多余灰边）。
- **工作目录卡片布局**：卡片网格水平居中，消除「最后一列右侧贴着滚动条」的留白；拖动缩放时若列数未变则跳过重排，减少卡片抖动。
- **下拉箭头图标修复**：项目卡片入口下拉框与原生下拉框均恢复显示朝下箭头（此前因 `image: none` 丢失）。
- **构建**：归档于 `构建\WPI-v1.8.0\`。

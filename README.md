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
- **三种输出格式**：
  - **PNG** — 整页高清截图，支持透明背景。
  - **GIF** — 逐帧录制页面动画（含转场、轮播、Hover），可选帧率。
  - **PDF** — 整页排版输出，适合存档与打印。
- **动画渲染**：完整播放页面动画；GIF 全帧录制，PNG / PDF 取动画结束后的终帧。
- **工作目录卡片流**：工作目录下的每个项目以彩色卡片展示，自动提取网站主色生成色卡，双击进入二级 / 三级子目录继续浏览，支持返回上级。
- **交互式预览**：内置预览窗口直接调用渲染内核，无需浏览器即可实时预览；也可在系统浏览器中打开静态服务地址（支持 F12 审查元素）。
- **尺寸语义清晰**：`宽度 = 浏览器视口宽度`，`高度 = 网页实际内容长度`；提供 2400 / 1440 / 1080 / 800 预设，支持任意自定义宽度。
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
2. **选择项目**：点击左侧项目卡片；卡片显示项目名、主色调色卡与操作按钮。
3. **预览确认**：点击「预览」在内置窗口查看页面；「浏览器打开」可在系统浏览器中 F12 审查元素。
4. **设置尺寸**：输入或选择导出宽度（高度跟随网页内容自动计算）。
5. **导出**：选择输出路径与格式，点击「导出」，等待动画播放完成后即可获取文件。

## 构建打包

```bash
python tools\build.py            # 构建 + 离线冒烟测试 + 归档
```

产出于 `工具所在盘\构建\WPI-v{version}\WPI.exe`（单文件可执行程序，含内置示例页与图标，体积约 200 MB 且已剔除未使用的 Qt 子系统）。

## 目录结构

```
WPI/
├── assets/                  # 应用图标（WPI.ico / WPI.png）
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
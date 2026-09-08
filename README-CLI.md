# WPI-noGUI-cli 使用说明

WPI 的**无 GUI 命令行版**:把本地前端网页(HTML + CSS + JS)或在线网站按指定宽度渲染,导出为 **PNG / GIF / MP4 / PDF**。与图形界面版(WPI-GUI.exe)共用同一条渲染与编码链路,但不带任何界面——适合脚本、定时任务、CI 流水线或服务器环境批量出图。

```
渲染内核:Playwright 驱动系统 Edge / Chrome(不内置浏览器)
编码链路:Pillow(全格式)+ FFmpeg(发现时用于 GIF 调色板与 MP4)
本体体积:约 66 MB,约为 GUI 版 1/3(已剔除全部 Qt / 界面代码)
```

## 环境要求

| 依赖 | 必需性 | 说明 |
|---|---|---|
| Microsoft Edge 或 Google Chrome | **必需** | 系统已装即可,自动探测(优先 Edge) |
| FFmpeg | 可选 | 本程序**不随附**。按 `WPI_FFMPEG` 环境变量 → 程序同级目录 → `PATH` 顺序发现 |
| (GIF 无 FFmpeg 时) | — | 自动回退 Pillow 编码,质量略低仍可用 |
| (MP4) | 必需 FFmpeg | 找不到 FFmpeg 时报错退出,不产出残缺文件 |

## 快速开始

```bat
:: 本地项目目录(内含 index.html)导出 PNG,宽度 1080
WPI-noGUI-cli.exe --source D:\web\my-page --output D:\out\my-page.png --width 1080

:: 在线网站导出 PNG
WPI-noGUI-cli.exe --source https://example.com --output out.png --width 1440

:: 录制动画 GIF(30 秒,25fps,无限循环)
WPI-noGUI-cli.exe --source D:\web\anim --output out.gif --format GIF --fps 25 --max-wait 30

:: 高清 MP4(X2 原生倍率,需要 FFmpeg)
WPI-noGUI-cli.exe --source D:\web\anim --output out.mp4 --format MP4 --fps 30 --scale 2

:: 打包为 PDF
WPI-noGUI-cli.exe --source D:\web\doc --output out.pdf --format PDF
```

进度与结果实时打印到控制台;成功以退出码 `0` 结束,可直接在脚本中判断。

## 参数一览

| 参数 | 默认 | 说明 |
|---|---|---|
| `--source` | 必填 | 源:HTML 文件、含 `index.html` 的项目目录,或 `http(s)://` URL |
| `--output` | 必填 | 输出文件路径(扩展名按 `--format` 自动校正) |
| `--format` | `PNG` | `PNG` / `GIF` / `MP4` / `PDF` |
| `--width` | `1080` | 浏览器视口宽度 px;高度始终跟随网页实际内容长度 |
| `--scale` | `1` | 分辨率倍率 `1/2/4/8`:布局不变、分辨率原生放大 |
| `--height` | `0`(不限) | 高度锁定 px:超出部分不导出、不压缩内容 |
| `--fps` | `25` | 帧速;GIF 用 `10/20/25/50`,MP4 用 `24/30/48/60` |
| `--loop` | `0` | GIF 循环次数,`0` = 无限循环 |
| `--max-wait` | `15` | 动画录制 / 等待时长上限(秒) |
| `--transparent` | 关 | PNG 保留透明背景(默认白底) |
| `--no-ffmpeg` | 关 | 强制禁用 FFmpeg(GIF 走 Pillow) |
| `--no-full-page` | 关 | 仅导出视口首屏(默认整页) |
| `--selfcheck` | — | 用内置示例页执行一次 PNG 导出,校验部署环境 |
| `--version` | — | 打印版本号 |

## 尺寸语义

- **宽度** = 浏览器视口宽度(即 `--width`)。
- **高度** = 网页实际内容长度,自动测量,无需指定。
- `--scale` 是原生渲染放大(浏览器 `deviceScaleFactor`),不是超分:页面仍按设定宽度排版,输出分辨率 × 倍率,X4/X8 适合印刷级长图。

## 动画导出行为

- **PNG / PDF**:导出前自动等待字体与图片加载、滚动触发 reveal-on-scroll 内容展开,并把有限动画收敛到终态后截取完整画面。
- **GIF / MP4**:录制整页同时播放的动画(含视口外 canvas),播放速度恒等于真实时间;录满 `--max-wait` 或动画提前停止即结束。

## 退出码

| 退出码 | 含义 |
|---|---|
| `0` | 导出成功 |
| `1` | 导出失败(浏览器内核缺失、无 FFmpeg、页面加载失败等,原因见 stderr) |
| `2` | 用法错误(缺少 `--source` / `--output` 等) |

## 与 GUI 版(WPI-GUI.exe)的差异

| | WPI-GUI.exe | WPI-noGUI-cli.exe |
|---|---|---|
| 图形界面 | 有(卡片工作区 / 预览 / 批量) | 无,纯命令行 |
| Qt / PySide6 | 包含 | 完全剔除(体积约 1/3) |
| FFmpeg | 同级目录随附 | 不随附(发现同级 / PATH 的则用) |
| 工作目录卡片、多选、批量导出 | 有 | 无(单条命令单文件;批量请用脚本循环) |
| 渲染 / 导出算法 | 同一套 | 同一套 |
| 控制台窗口 | 仅 `--export` 模式输出 | 常驻控制台输出 |

## 常见问题

- **提示未检测到浏览器内核**:安装 Microsoft Edge 或 Google Chrome 后重试;也可设 `WPI_BROWSER_CHANNEL=chrome|msedge` 指定通道。
- **MP4 报"需要 FFmpeg"**:把 `ffmpeg.exe` 放到本程序同级目录,或设环境变量 `WPI_FFMPEG` 指向其完整路径,或加入 `PATH`。
- **在线网站登录态**:WPI 使用独立的持久化浏览器目录(`%LOCALAPPDATA%\WPI\browser-profile`,可用 `WPI_PROFILE_DIR` 覆盖),cookies 在多次导出间保留,且对系统浏览器配置零读写。本程序以无头模式访问页面,没有交互登录入口;需要登录才能看的页面不适合直接导出。
- **首次运行较慢**:单文件程序需解压,属正常现象。

## License

[MIT](https://github.com/GreenChennai/WPI/blob/main/LICENSE)

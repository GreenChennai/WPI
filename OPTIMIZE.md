# WPI v3.0.3 优化清单

> 目标：GIF/MP4 恢复**整页同时动画**（整页竖长版式，非正方形视口 + 滚动播放），且下方折叠区 canvas 动画（噪波墨流 / 入水扩散 / 文字裂变解构）流畅、同步、无闪烁。
> 文件：src/core/capture_engine.py、src/core/controller.py、OPTIMIZE.md
> 关联：V3.0.2 用「滚动逐帧录制」解决了闪烁但产物变成正方形视口 + 滚动播放动画，用户不接受，要求整页版式。

---

## 优化项列表

### 1. GIF/MP4 恢复整页同时动画：整页截图 + 视口外 canvas 实时位图合成
- **现状**：V3.0.2 的滚动逐帧录制产物是正方形视口 + 滚动播放动画，用户明确不接受；要求整页（竖长版式）同时动画，宁可导出时间长。
- **根因**（已复现）：整页单拍 `captureBeyondViewport` 对视口外的 2D canvas 不刷新光栅——canvas 的 JS 位图在更新（每 33ms 一帧），但 Chromium 合成器只在它处于屏内时才提交纹理，整页单拍取到的是陈旧/欠渲染帧（实测下方折叠流场暗像素 ~1132 vs 在屏 ~3000-5100）。已系统排查替代方案：
  - 原生 rAF 不节流可保在屏/屏外纹理都新鲜，但密集 canvas（INK 7 个 canvas 163fps+）占满主线程导致 `evaluate` 饿死、导出永久卡死（不可用）。
  - rAF 保留式节流（wrap 原生 rAF + perf.now 限速）在 ≤30fps 时视口外光栅**彻底冻结**（无头模式 rAF 时间戳几乎不动，`ts-last` 判据会永久停摆；即使用 perf.now 限速，合成器仍要求画布逐帧连续绘制才刷新屏外纹理）——不可用。
  - `HeadlessExperimental.beginFrame`（overcrank 方案）在新 headless 已被移除；旧 headless shell / Firefox 未安装（需下载，依赖变更过大）。
- **修复**：新增 `CaptureEngine.capture_full_page_frames()`——每帧先从页面**同一次 evaluate** 读取视口外 canvas 的实时位图（`canvas.toDataURL`，天然同步到同一动画时刻），再整页单拍（CDP JPEG 加速），把实时位图按页面坐标合成到整页图上（`_canvas_snapshots` / `_compose_canvases`）。rAF 全程保持 33ms 节流（INK 不卡死），canvas 动画以 ~30fps 播放，逐帧采样即得**整页同时动画**且各 canvas 相互同步。视口内 canvas 由合成器实时刷新故跳过；带 transform / 非 normal 混合模式的 canvas 无法平面粘贴还原而跳过（保留截图像素）；CSS opacity 按透明度合成。
- **说明**：合成只改动 canvas 区域，其余像素与整页截图逐字节一致（已断言验证）；静态导出（PNG）仍走 V3.0.2 的分块滚动截取（`force_tiled`），不受影响。
- **验证**：INKFLOW 800px 整页 GIF 70 帧 800x3431（整页竖长版式），流场区逐帧变化 39/39、墨滴 39/39，无闪烁；INK 800x7577 整页 GIF 不卡死；MP4（FFmpeg）同源编码，抽帧验证流场逐帧变化 5/5；demo PNG/GIF/PDF 回归通过；高度锁定 `height` 对整页帧按设备像素裁剪生效（800x1500）。pytest 46/46。
- **状态**：✅ 已完成

### 2. 版本号升级到 3.0.3
- **目标**：`src/config/presets.py`、`pyproject.toml`、`tools/build.py`、workflow 版本段统一改为 3.0.3。
- **状态**：✅ 已完成

---

## 依赖关系

- 项 1 在 V3.0.2「滚动逐帧录制」基础上替换为「整页截图 + 视口外 canvas 位图合成」，保持 33ms rAF 节流不回归 INK 卡死问题。
- 项 2 依赖项 1 完成后统一改版号。

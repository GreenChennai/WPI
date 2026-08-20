# WPI v3.0.0 优化清单

> 目标：① 修复重交互静态网页导出 PNG 卡死（40% 无法前进）；② 超时不强制退出，改为提醒 + 「取消任务」一键中止
> 文件：src/、.github/workflows/、OPTIMIZE.md
> 关联：静态导出可靠性 + 导出流程可取消

---

## 优化项列表

### 1. 修复重交互页面 PNG 导出卡死（40% 卡在 settle）
- **现状**：从 `2026-08-16_INK_墨迹实验室`（7 个 canvas rAF 动画循环 + `scroll-behavior: smooth` + 无限 CSS 动画）以 800px 导出 PNG 卡在 40%（`settle()` 内）数分钟无进展。
- **根因**（已定位并复现）：无头模式下 `requestAnimationFrame` 不锁 60fps，密集 rAF 画布动画以数百 fps（实测 163fps+）占满渲染主线程。`page.evaluate` 中 `await` 的续跑与 Playwright 自带超时都建立在页面主线程能调度任务之上——主线程被占满时两者同时失效，evaluate 永不返回 → 导出卡死固定百分比。`scroll-behavior: smooth` 会让每次 scrollTo 走平滑动画，成为卡死放大器（滚动遍历每步实测 6s+）。
- **修复**：
  1. 静态导出（PNG/PDF）加载前注入脚本把 rAF 节流到 ~4fps（`STATIC_RENDER_RAF_THROTTLE_MS=250`）+ `emulate_media(reduced_motion='reduce')` 让页面「最小动效」降级生效（GIF/MP4 需完整动画，不节流）。
  2. `trigger_scroll_reveals` 强制 `scroll-behavior: auto` 瞬时滚动 + 步数上限（`SCROLL_REVEAL_MAX_STEPS=40`）兜底超长页。
- **验证**：INK 页 800px 导出 5.1s 完成（800×7577 整页、内容非空白）；demo PNG/PDF/GIF 回归通过。
- **状态**：✅ 已完成

### 2. 超时提醒（不强制退出）+ 「取消任务」按钮
- **现状**：批量导出看门狗超时（900s）直接抛错中止；GUI 导出进行中无取消入口。
- **修复**：
  1. `run_batch_sync` 看门狗超时**不再中止**——任务量大 / 机器弱属正常慢，改为状态栏提醒「可继续等待，或点击「取消任务」中止」，继续等待直到完成或取消。
  2. 新增 `ExportCancelledError` + `cancel_event` 贯穿 `run_export_sync` / `run_batch_sync` / 长耗时捕获循环（`capture_frames` / `capture_scroll_frames` / `capture_highres`），各阶段检查取消标志即抛。
  3. GUI 在「导出中…」按钮右侧新增「取消任务」按钮：导出中显示，点击置取消标志并正常中止，完成弹「已取消」提示。
- **验证**：预置取消标志 → 立即取消；导出中 1.7s 内取消生效；取消与失败（`failed`）区分信号（`cancelled`）。
- **状态**：✅ 已完成

### 3. 版本号升级到 3.0.0
- **现状**：`src/config/presets.py`、`pyproject.toml`、`tools/build.py`、workflow 版本段四处仍为 2.9.0。
- **目标**：统一改为 3.0.0。
- **状态**：✅ 已完成

### 4. 提交推送 + Actions 验证
- **现状**：本地待推送。
- **目标**：提交推送、验证 Actions 构建通过并生成 Release。
- **状态**：⬜ 待执行

---

## 依赖关系

- 项 1、2 相互独立（1 修卡死、2 改取消/提醒），可并行。
- 项 3 依赖 1-2 完成后统一改版号。
- 项 4 依赖 1-3 全部完成。
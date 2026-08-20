# WPI v3.0.1 优化清单

> 目标：① 修复 PNG 静态导出时一次性 JS 动画（打字机 / 墨水晕开）未播完就截图；② 修复 INK 墨迹实验室页 GIF/MP4 导出仍卡 40%；③ 「取消任务」按钮改红色 + 取消后进度归 0%；④ 「更换目录…」按钮改黄色
> 文件：src/、OPTIMIZE.md
> 关联：V3.0.0 用「250ms 节流 + reduced-motion」修好了 INK 页 PNG 卡死，但把一次性动画截断了

---

## 优化项列表

### 1. 修复 PNG 静态导出一次性动画被截断（打字机 / 墨水晕开）
- **现状**：INKFLOW 墨流实验室 800px 导出 PNG，打字机（setTimeout 驱动，~41 字符 ~4s）只打了几字符、墨滴扩散（逐帧 rAF 增长）没晕开。INK 墨迹实验室页 PNG 正常。
- **根因**（V3.0.1 探测确认）：V3.0.0 对静态导出用 250ms(4fps) 节流 + `reduced_motion='reduce'`。reduced-motion 的 CSS 折叠让 `freeze_animations()` 返回 inf=0 → settle 走 300ms 兜底就截图，打字机没等完；墨滴逐帧增长在 4fps 下要 ~17s 才晕开。`getAnimations()` 看不到 setTimeout/rAF 驱动的一次性动效，只能靠「画面稳定」判定。
- **修复**：
  1. rAF 节流由 250ms 改为 33ms（~30fps）并**应用到所有格式**（`RENDER_RAF_THROTTLE_MS=33`）：一次性 rAF 动效仍能在数秒内播完，同时消除主线程被占满导致的 evaluate 饿死。
  2. `settle()`：inf>0（有无限 CSS 动画）时等 3s + 再滚动 + 冻结 + 再等 3s（JS 一次性动效有足够时间播完）；inf==0 时调用新增的 `wait_visual_stability()`——0.5s 采样整页像素，连续 3 帧不变视为稳定（打字机、墨滴等 JS 动效靠像素不变兜底等完），预算 `ANIMATION_SETTLE_MAX_WAIT=6.0s`。
  3. `trigger_scroll_reveals()` 改为 **Python 驱动**（同步 scrollTo + sleep）：页面侧 async 循环的 await 在密集 rAF 页面会被饿死（evaluate 永不返回），同步注入-执行-返回稳定可靠；配合 `scroll-behavior:auto` 与 `SCROLL_REVEAL_MAX_STEPS` 步数上限。
- **验证**：INKFLOW 800px PNG 导出后 evaluate 实测打字机 41/41 字符完整、墨滴 47k+ 像素、hero 墨团 216k 像素（alpha≤29 为设计值）。
- **状态**：✅ 已完成

### 2. 修复 INK 墨迹实验室页 GIF/MP4 导出卡 40%
- **现状**：GIF/MP4 走完整动画路径（不节流 rAF、不 reduced-motion），INK 页 7 个 canvas rAF 循环以数百 fps 占满主线程，`trigger_scroll_reveals()` 的页面侧 async 循环与 `wait_assets` 的 evaluate 同时饿死 → 卡在 40%。
- **根因**：GIF/MP4 分支仍用 V2.9 的页面侧 async 滚动循环 + 无 rAF 节流。
- **修复**：同上——rAF 节流 33ms 应用到所有格式（含 GIF/MP4）+ `trigger_scroll_reveals` 改 Python 驱动。INK 页 33ms 节流 + 同步滚动实测完成（4.7s），墨滴逐帧扩散仍完整。
- **验证**：INK 800px GIF（fps10）35s 完成、MP4 路径同链路；demo GIF 9.2s 完成。
- **状态**：✅ 已完成

### 3. 「取消任务」按钮改红色 + 取消后进度条归 0%
- **现状**：取消按钮为 ghost 灰框，取消后进度条残留取消前百分比。
- **修复**：新增 `QPushButton#dangerBtn`（红底白字 `DANGER_STRONG` + hover/press 派生色），`cancel_btn` 改对象名 "dangerBtn"；`_on_cancel_clicked` 与 `_on_export_cancelled` 中 `progress.setValue(0)`。
- **状态**：✅ 已完成

### 4. 「更换目录…」按钮改黄色
- **现状**：更换目录按钮为 ghost 灰框，视觉上不突出。
- **修复**：新增 `QPushButton#warningBtn`（黄底白字 `WARNING` + hover/press 派生色），`chdir_btn` 改对象名 "warningBtn"。
- **状态**：✅ 已完成

### 5. 版本号升级到 3.0.1
- **目标**：`src/config/presets.py`、`pyproject.toml`、`tools/build.py`、workflow 版本段统一改为 3.0.1。
- **状态**：✅ 已完成

---

## 依赖关系

- 项 1、2 共享同一套修复（rAF 节流 33ms + Python 驱动滚动 + 画面稳定等待），同步落地。
- 项 3、4 独立（GUI 样式），可并行。
- 项 5 依赖 1-4 全部完成后统一改版号。
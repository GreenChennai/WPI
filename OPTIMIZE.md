# WPI v2.9.0 优化清单

> 目标：修复 CI 构建失败 + 批量导出卡死防护 + 在线网站登录态保留
> 文件：src/、tools/、.github/workflows/、README.md
> 关联：GitHub Actions 发行流程

---

## 优化项列表

### 1. 修复 GitHub Actions 构建失败（离线冒烟 UnicodeEncodeError）
- **现状**：CI 上 PyInstaller 打包成功，但冒烟 `smoke.png` rc=1，exe 输出 `导出失败: UnicodeEncodeError: 'charmap' codec can't encode characters in position 9-16`。
- **根因**：windowed 冻结态 `_attach_parent_console()` 中 `AttachConsole(-1)` 失败时只返回 0 不抛异常，随后 `open("CONOUT$")` 静默失败，stdout 保持为 PyInstaller 按 locale 编码（英文 runner 为 cp1252）打开的重定向管道——打印中文状态即崩溃；本地中文系统（cp936）编码中文字符因此无法复现。
- **修复**：`_attach_parent_console()` 检查 AttachConsole 返回值；无论成败都把 stdout/stderr 收敛为可写中文的 UTF-8 流（None 兜底 CONOUT$/devnull、附着时指到控制台、重定向时 reconfigure 为 UTF-8）。workflow env 追加 `PYTHONIOENCODING=utf-8`。
- **状态**：✅ 已完成

### 2. 多选导出 PNG 卡死防护
- **现状**：用户反馈多选导出 PNG 卡在 8% 无法导出。用 demo 在主线程与 QThread 下批量（2/3/6 项、X1/X2）复现均正常完成，无法本地复现原问题。
- **防护**：`run_batch_sync` 每项在独立守护线程执行并套看门狗（`BATCH_ITEM_TIMEOUT_SECONDS=900`），超时抛明确错误中止，杜绝 GUI 无限等待；Playwright 各步骤本身有 30s 超时兜底。
- **状态**：✅ 已完成（仍需用户用真实项目验证；若仍出现，请提供最小复现项目）

### 3. 在线网站导出保留登录态 / 降低人机校验
- **现状**：在线网站导出用 Playwright 临时上下文，无 cookie，访问需登录/有人机校验的站点退到登录页、验证页。
- **修复**：`BrowserHost` 支持持久化用户目录（`use_profile=True`，仅在线 URL 启用）；数据落在 `%LOCALAPPDATA%\WPI\browser-profile`（可 `WPI_PROFILE_DIR` 覆盖），与系统浏览器完全隔离；隐藏自动化标记（`--disable-blink-features=AutomationControlled`、忽略 `--enable-automation`）降低校验误判；目录被占用时降级为临时上下文保证导出可用。
- **验证**：两次独立启动写/读 cookie 成功持久化。
- **状态**：✅ 已完成

### 4. 版本号升级到 2.9.0
- **现状**：`src/config/presets.py`、`pyproject.toml`、`tools/build.py`、workflow 版本段四处仍为 2.8.0。
- **目标**：统一改为 2.9.0。
- **状态**：✅ 已完成（本地构建 `WPI-v2.9.0-7a598e5\`，冒烟全通过）

### 5. 提交推送 + Actions 验证
- **现状**：本地待推送。
- **目标**：提交推送、验证 Actions 构建通过并生成 Release。
- **状态**：⬜ 待执行

---

## 依赖关系

- 项 1/2/3 相互独立，可并行排查。
- 项 4 依赖 1-3 修复完成后再统一改版号。
- 项 5 依赖 1-4 全部完成。

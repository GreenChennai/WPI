# WPI v2.8.0 优化清单

> 目标：注释重写 + 代码质量清理 + 版本升级 + 测试排除 + README 精简 + CI 自动构建发行
> 文件：src/、tools/、README.md、.gitignore
> 关联：GitHub Actions 发行流程

---

## 优化项列表

### 1. 注释重写（全部源码）
- **现状**：全库注释以「v1.x/v2.x：改动说明」的版本号式写法为主，描述"改了什么"而非"代码干什么、为什么这样写"。
- **目标**：改为「功能 + 原因」式注释；关键算法（JPEG CDP 采样、真实时间播放、PDF 分页、单端口挂载、单实例锁、PyInstaller 瘦身）保留深入说明；去除版本号痕迹。
- **状态**：✅ 已完成（commit cadd05a，全库 23 文件去版本号化，改为功能+原因）

### 2. 代码质量清理
- **现状**：`style.py` 存在空壳函数 `apply_object_names()`（现由控件直接 setObjectName）；`primary_style()` 疑为未使用备用代码；`main.py` 有 `if True:` 包装语句；`presets.py` 尾部有遗留死注释。
- **目标**：删除未使用/空壳代码，消除 `if True:` 代码异味，清理死注释。
- **状态**：✅ 已完成（commit a3984ad）

### 3. 版本号升级到 2.8.0
- **现状**：`src/config/presets.py`、`pyproject.toml`、`tools/build.py` 三处仍为 2.7.0。
- **目标**：统一改为 2.8.0。
- **状态**：✅ 已完成（commit e903f2e）

### 4. tests 测试文件不随仓库同步
- **现状**：`tests/` 已提交进 git（7 个文件）。
- **目标**：`.gitignore` 加入 `tests/`，`git rm -r --cached tests`，此后测试文件仅存本地。
- **状态**：✅ 已完成（commit cedd3d4，tests/ 已从 git 移除并加入 .gitignore）

### 5. README「功能特性」精简
- **现状**：约 25 行冗长纯文字描述，细节堆砌。
- **目标**：精简为结构化关键特性列表（保留真实功能与用户关心的点），删去赘述。
- **状态**：✅ 已完成（commit 951769f，功能特性精简为 9 条关键项，同步目录结构/测试/构建说明）

### 6. GitHub Actions 自动构建 + Release
- **现状**：无 CI，版本由本地 `tools/build.py` 手动构建。
- **目标**：新增 workflow：Windows 上 PyInstaller 打包 → 下载 gyan.dev ffmpeg → 打 zip（exe + ffmpeg + README + VERSION.txt）→ 创建 GitHub Release 并上传资产。
- **状态**：✅ 已完成（commit e9f97c9）

### 7. 提交推送 + 本地构建验证
- **现状**：本地待推送。
- **目标**：提交推送、本地构建到 `E:\平日资料\构建`，验证 Actions 触发。
- **状态**：🔄 进行中

---

## 依赖关系

- 项 2 先于项 1 执行（先删死代码，避免给即将删除的代码写注释）。
- 项 3 可随时执行，独立。
- 项 4 独立，尽早执行避免 tests 干扰后续提交。
- 项 5/6 独立。
- 项 7 依赖 1-6 全部完成。

"""WPI 设置文件（v1.4.0）。

在软件同级目录维护 `WPI_settings.json`：启动时检测是否已存在，
不存在则创建并写入默认值；存在则读取回填到界面。
记录内容：工作目录位置、导出宽度、最近输出文件位置。
零依赖模块（不引入 Qt），便于单元测试。
"""

from __future__ import annotations

import json
import os

from config.presets import DEFAULT_WIDTH, app_base_dir, default_workspace_dir

SETTINGS_NAME = "WPI_settings.json"

# 已知键默认值（新增键朝后追加，旧文件缺少的键自动补默认值）
DEFAULTS: dict = {
    "workspace_dir": "",       # 留空 = 使用默认 WorkerFile 目录
    "width": DEFAULT_WIDTH,    # 导出宽度（px）
    "output_path": "",         # 最近一次导出文件位置
    "output_dir": "",          # 最近一次导出所在目录（兼容旧字段）
}


class Settings:
    """读写软件同级目录的 JSON 设置文件。"""

    def __init__(self, path: str | None = None):
        self.path = path or os.path.join(app_base_dir(), SETTINGS_NAME)
        self.data: dict = dict(DEFAULTS)
        self.load()

    # ---------------------------------------------------------------- 读写
    def load(self) -> None:
        """读取设置；文件缺失时按默认值创建。"""
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                stored = json.load(fh)
            if isinstance(stored, dict):
                self.data = {**dict(DEFAULTS), **stored}
            else:
                self.data = dict(DEFAULTS)
        except (OSError, ValueError, TypeError):
            self.data = dict(DEFAULTS)
        self.save_if_missing()

    def save_if_missing(self) -> None:
        if os.path.isfile(self.path):
            return
        self.save()

    def save(self) -> None:
        try:
            with open(self.path, "w", encoding="utf-8") as fh:
                json.dump(self.data, fh, ensure_ascii=False, indent=2)
        except OSError:
            pass  # 无法写入时静默（不影响主流程）

    # ---------------------------------------------------------------- 取值
    @property
    def workspace_dir(self) -> str:
        """返回有效的工作目录；配置无效时回退默认 WorkerFile。"""
        value = str(self.data.get("workspace_dir") or "").strip()
        if value and os.path.isdir(value):
            return os.path.abspath(value)
        return default_workspace_dir()

    @workspace_dir.setter
    def workspace_dir(self, path: str) -> None:
        self.data["workspace_dir"] = os.path.abspath(path) if path else ""
        self.save()

    @property
    def width(self) -> int:
        try:
            return max(1, int(self.data.get("width", DEFAULT_WIDTH)))
        except (TypeError, ValueError):
            return DEFAULT_WIDTH

    @width.setter
    def width(self, value: int) -> None:
        self.data["width"] = int(value)
        self.save()

    @property
    def output_path(self) -> str:
        value = str(self.data.get("output_path") or "").strip()
        if value:
            return value
        return str(self.data.get("output_dir") or "").strip()

    @output_path.setter
    def output_path(self, path: str) -> None:
        if path:
            self.data["output_dir"] = os.path.dirname(os.path.abspath(path))
        self.data["output_path"] = path or ""
        self.save()
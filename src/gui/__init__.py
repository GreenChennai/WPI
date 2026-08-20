"""gui 包：各组件模块按需直接导入。

此前 `from .preview_window import *` 会在任何 `import gui` / 导入子模块时
提前加载 QtWebEngine 等重型模块；现已改为按需导入，加速启动、降低占用。
"""
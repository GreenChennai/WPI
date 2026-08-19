"""工作目录项目扫描 / 默认目录测试（v1.1.0 UI 改造）。"""

import os

from gui.workspace_panel import WorkspacePanel


def _make_project(root: str, name: str) -> str:
    d = os.path.join(root, name)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as fh:
        fh.write("<!DOCTYPE html><html><body>hi</body></html>")
    return d


def test_scan_projects(tmp_path):
    _make_project(str(tmp_path), "site-a")
    _make_project(str(tmp_path), "site-b")
    os.makedirs(os.path.join(str(tmp_path), "no-index"), exist_ok=True)
    with open(os.path.join(str(tmp_path), "plain.html"), "w", encoding="utf-8") as fh:
        fh.write("<html></html>")

    found = WorkspacePanel._scan_projects(str(tmp_path))
    names = {os.path.basename(p) for p in found}
    assert names == {"site-a", "site-b"}


def test_default_workspace_dir_created(tmp_path, monkeypatch):
    from config import presets

    monkeypatch.setattr(presets, "app_base_dir", lambda: str(tmp_path))
    d = presets.default_workspace_dir()
    assert d == os.path.join(str(tmp_path), "WorkerFile")
    assert os.path.isdir(d)


def test_workerfile_name():
    from config.presets import WORKERFILE_NAME

    assert WORKERFILE_NAME == "WorkerFile"


def test_app_title_is_website():
    from config.presets import APP_TITLE

    assert APP_TITLE == "Website Page to Image"


def test_scan_entries_splits_projects_and_folders(tmp_path):
    """无 index.html 的文件夹应作为二级工作目录（不可点击为项目）。"""
    _make_project(str(tmp_path), "site-a")
    os.makedirs(os.path.join(str(tmp_path), "plain-folder"), exist_ok=True)

    projects, folders = WorkspacePanel._scan_entries(str(tmp_path))
    projects_names = {os.path.basename(p) for p in projects}
    folders_names = {os.path.basename(p) for p in folders}
    assert projects_names == {"site-a"}
    assert folders_names == {"plain-folder"}


def test_scan_entries_three_levels(tmp_path):
    """三层嵌套：每层里的项目都应能被扫描到。"""
    a = os.path.join(str(tmp_path), "a")
    b = os.path.join(a, "b")
    _make_project(b, "deep-site")

    _p1, f1 = WorkspacePanel._scan_entries(str(tmp_path))
    assert f1 == [a]

    _p2, f2 = WorkspacePanel._scan_entries(f1[0])
    assert f2 == [b]

    p3, f3 = WorkspacePanel._scan_entries(f2[0])
    assert {os.path.basename(x) for x in p3} == {"deep-site"}
    assert f3 == []


def _make_many_projects(root: str, n: int) -> list[str]:
    return [_make_project(root, f"site-{i:02d}") for i in range(n)]


def _panel_with_projects(tmp_path, n: int) -> "WorkspacePanel":
    from PySide6.QtWidgets import QApplication

    _make_many_projects(str(tmp_path), n)
    app = QApplication.instance() or QApplication([])
    panel = WorkspacePanel()
    panel.set_workdir(str(tmp_path))
    app.processEvents()
    return panel


def test_reflow_shows_more_columns_when_wide(tmp_path):
    """v1.4.0：面板加宽后每行卡片数应大于 3（自适应排版）。"""
    panel = _panel_with_projects(tmp_path, 8)
    panel.resize(960, 700)
    panel.show()
    panel._reflow()
    panel._grid.activate()
    # 计算期望列数
    avail = panel._scroll.viewport().width() - 32 - panel._grid.spacing()
    card_w = 168 + panel._grid.spacing()
    expect_cols = max(1, (avail + panel._grid.spacing()) // card_w)
    rows = panel._grid.rowCount()
    assert rows >= 1
    assert panel._grid.count() == 8
    assert expect_cols >= 4, f"宽面板应至少 4 列，实际 {expect_cols}"


def test_reflow_narrow_panel_falls_back_columns(tmp_path):
    """v1.4.0：面板较窄时每行卡片数减少（至少 1 列）。"""
    panel = _panel_with_projects(tmp_path, 5)
    panel.resize(240, 700)
    panel.show()
    panel._reflow()
    panel._grid.activate()
    assert panel._grid.count() == 5
    assert panel._grid.rowCount() >= 1

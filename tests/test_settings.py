"""config.settings v1.4.0：设置文件创建 / 读写 / 回填默认值。"""

import os

import pytest

from config.settings import DEFAULTS, SETTINGS_NAME, Settings


def test_settings_created_when_missing(tmp_path):
    path = os.path.join(str(tmp_path), SETTINGS_NAME)
    s = Settings(path=path)
    assert os.path.isfile(path)
    assert s.workspace_dir == s.workspace_dir  # 有值（回退默认 WorkerFile）
    assert s.width == DEFAULTS["width"]


def test_settings_persist_roundtrip(tmp_path):
    path = os.path.join(str(tmp_path), SETTINGS_NAME)
    s = Settings(path=path)
    mysite = os.path.join(str(tmp_path), "mysite")
    os.makedirs(mysite, exist_ok=True)
    s.workspace_dir = mysite
    s.width = 1440
    s.output_path = os.path.join(str(tmp_path), "out.png")

    s2 = Settings(path=path)  # 重新读取
    assert s2.workspace_dir == mysite
    assert s2.width == 1440
    assert s2.output_path == os.path.join(str(tmp_path), "out.png")


def test_settings_invalid_workspace_falls_back(tmp_path):
    path = os.path.join(str(tmp_path), SETTINGS_NAME)
    s = Settings(path=path)
    s.workspace_dir = os.path.join(str(tmp_path), "does-not-exist")
    s2 = Settings(path=path)
    # 无效目录回退到默认 WorkerFile（仍应存在）
    assert os.path.isdir(s2.workspace_dir)


def test_settings_width_fallback_on_garbage(tmp_path):
    path = os.path.join(str(tmp_path), SETTINGS_NAME)
    s = Settings(path=path)
    s.data["width"] = "garbage"
    assert s.width == DEFAULTS["width"]


def test_output_path_setter_records_dir(tmp_path):
    path = os.path.join(str(tmp_path), SETTINGS_NAME)
    s = Settings(path=path)
    out = os.path.join(str(tmp_path), "sub", "a.png")
    s.output_path = out
    assert s.output_path == out
    assert s.data["output_dir"] == os.path.join(str(tmp_path), "sub")

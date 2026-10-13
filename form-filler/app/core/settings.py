"""应用设置 — 保存在数据目录的 settings.json（如是否已完成新手引导）"""

from __future__ import annotations


import os
import json

from app.core.storage import atomic_write_json

DEFAULT_SETTINGS = {
    "onboarding_done": False,
}


def _path(data_dir: str) -> str:
    return os.path.join(data_dir, "settings.json")


def load_settings(data_dir: str) -> dict:
    """读取设置；文件不存在或损坏时返回默认值"""
    path = _path(data_dir)
    if not os.path.exists(path):
        return dict(DEFAULT_SETTINGS)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError):
        return dict(DEFAULT_SETTINGS)
    merged = dict(DEFAULT_SETTINGS)
    merged.update(data or {})
    return merged


def save_settings(data_dir: str, settings: dict):
    """保存设置（原子写）"""
    atomic_write_json(_path(data_dir), settings)

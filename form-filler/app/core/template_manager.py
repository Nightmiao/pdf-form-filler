"""模板管理器 — 模板的创建、读取、更新、删除，以及数据持久化

序列化统一走 TemplateMeta.to_dict() / from_dict()（含字段校验清洗），
避免与 .lmt 导入导出逻辑重复。
"""

from __future__ import annotations


import os
import json
import shutil
from datetime import datetime
from typing import Optional

from app.core.field_model import TemplateMeta, PageSettings
from app.core.pdf_engine import get_page_count, render_thumbnail


class TemplateManager:
    """管理表单模板的生命周期"""

    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.templates_dir = os.path.join(data_dir, "templates")
        self._ensure_dir(self.templates_dir)

    # ── 基础工具 ──────────────────────────────────

    def _ensure_dir(self, path: str):
        os.makedirs(path, exist_ok=True)

    def template_dir(self, template_id: str) -> str:
        return os.path.join(self.templates_dir, template_id)

    def json_path(self, template_id: str) -> str:
        return os.path.join(self.template_dir(template_id), "template.json")

    def pdf_path(self, template_id: str) -> str:
        return os.path.join(self.template_dir(template_id), "original.pdf")

    def thumb_path(self, template_id: str) -> str:
        return os.path.join(self.template_dir(template_id), "thumbnail.png")

    # ── 模板操作 ──────────────────────────────────

    def create(self, name: str, pdf_source_path: str) -> TemplateMeta:
        """从 PDF 文件创建新模板"""
        meta = TemplateMeta(name=name)
        meta.page_count = get_page_count(pdf_source_path)
        meta.page_settings = [PageSettings() for _ in range(meta.page_count)]
        meta.original_file = "original.pdf"
        now = datetime.now().isoformat()
        meta.created_at = now
        meta.updated_at = now

        self._ensure_dir(self.template_dir(meta.id))
        shutil.copy2(pdf_source_path, self.pdf_path(meta.id))

        thumb = render_thumbnail(self.pdf_path(meta.id), 0)
        thumb.save(self.thumb_path(meta.id), "PNG")

        self._save_meta(meta)
        return meta

    def get(self, template_id: str) -> Optional[TemplateMeta]:
        path = self.json_path(template_id)
        if not os.path.exists(path):
            return None
        return self._load_meta(path)

    def list_all(self) -> list[TemplateMeta]:
        templates = []
        if not os.path.exists(self.templates_dir):
            return templates
        for dirname in os.listdir(self.templates_dir):
            path = self.json_path(dirname)
            if os.path.exists(path):
                meta = self._load_meta(path)
                if meta:
                    templates.append(meta)
        templates.sort(key=lambda t: t.updated_at, reverse=True)
        return templates

    def update(self, meta: TemplateMeta):
        meta.updated_at = datetime.now().isoformat()
        self._save_meta(meta)

    def delete(self, template_id: str):
        template_dir = self.template_dir(template_id)
        if os.path.exists(template_dir):
            shutil.rmtree(template_dir)

    def rename(self, template_id: str, new_name: str):
        meta = self.get(template_id)
        if meta:
            meta.name = new_name
            self.update(meta)

    def get_pdf_path(self, template_id: str) -> str:
        return self.pdf_path(template_id)

    def get_thumbnail_path(self, template_id: str) -> str:
        path = self.thumb_path(template_id)
        if os.path.exists(path):
            return path
        return ""

    def search(self, keyword: str) -> list[TemplateMeta]:
        all_templates = self.list_all()
        if not keyword:
            return all_templates
        kw = keyword.lower()
        return [t for t in all_templates if kw in t.name.lower()]

    # ── 内部方法 ──────────────────────────────────

    def _save_meta(self, meta: TemplateMeta):
        with open(self.json_path(meta.id), "w", encoding="utf-8") as f:
            json.dump(meta.to_dict(), f, ensure_ascii=False, indent=2)

    def _load_meta(self, json_path: str) -> Optional[TemplateMeta]:
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError):
            return None
        try:
            return TemplateMeta.from_dict(data)
        except Exception:
            return None
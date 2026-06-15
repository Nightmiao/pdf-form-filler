"""模板管理器 — 模板的创建、读取、更新、删除，以及数据持久化"""

import os
import json
import shutil
from datetime import datetime
from typing import Optional

from app.core.field_model import TemplateMeta, FieldDefinition, PageSettings
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

    def _template_dir(self, template_id: str) -> str:
        return os.path.join(self.templates_dir, template_id)

    def _json_path(self, template_id: str) -> str:
        return os.path.join(self._template_dir(template_id), "template.json")

    def _pdf_path(self, template_id: str) -> str:
        return os.path.join(self._template_dir(template_id), "original.pdf")

    def _thumb_path(self, template_id: str) -> str:
        return os.path.join(self._template_dir(template_id), "thumbnail.png")

    # ── 模板操作 ──────────────────────────────────

    def create(self, name: str, pdf_source_path: str) -> TemplateMeta:
        """从 PDF 文件创建新模板

        Args:
            name: 模板名称
            pdf_source_path: 源 PDF 文件路径

        Returns:
            新创建的 TemplateMeta
        """
        meta = TemplateMeta(name=name)
        meta.page_count = get_page_count(pdf_source_path)
        meta.page_settings = [PageSettings() for _ in range(meta.page_count)]
        meta.original_file = "original.pdf"
        now = datetime.now().isoformat()
        meta.created_at = now
        meta.updated_at = now

        # 创建模板目录
        template_dir = self._template_dir(meta.id)
        self._ensure_dir(template_dir)

        # 复制 PDF
        shutil.copy2(pdf_source_path, self._pdf_path(meta.id))

        # 生成缩略图
        thumb = render_thumbnail(self._pdf_path(meta.id), 0)
        thumb.save(self._thumb_path(meta.id), "PNG")

        # 保存 JSON
        self._save_meta(meta)
        return meta

    def get(self, template_id: str) -> Optional[TemplateMeta]:
        """获取模板"""
        path = self._json_path(template_id)
        if not os.path.exists(path):
            return None
        return self._load_meta(path)

    def list_all(self) -> list[TemplateMeta]:
        """列出所有模板"""
        templates = []
        if not os.path.exists(self.templates_dir):
            return templates
        for dirname in os.listdir(self.templates_dir):
            path = self._json_path(dirname)
            if os.path.exists(path):
                meta = self._load_meta(path)
                if meta:
                    templates.append(meta)
        # 按更新时间倒序
        templates.sort(key=lambda t: t.updated_at, reverse=True)
        return templates

    def update(self, meta: TemplateMeta):
        """更新模板（保存到文件）"""
        meta.updated_at = datetime.now().isoformat()
        self._save_meta(meta)

    def delete(self, template_id: str):
        """删除模板及其所有数据"""
        template_dir = self._template_dir(template_id)
        if os.path.exists(template_dir):
            shutil.rmtree(template_dir)

    def rename(self, template_id: str, new_name: str):
        """重命名模板"""
        meta = self.get(template_id)
        if meta:
            meta.name = new_name
            self.update(meta)

    def get_pdf_path(self, template_id: str) -> str:
        """获取模板的原始 PDF 路径"""
        return self._pdf_path(template_id)

    def get_thumbnail_path(self, template_id: str) -> str:
        """获取缩略图路径"""
        path = self._thumb_path(template_id)
        if os.path.exists(path):
            return path
        return ""

    def search(self, keyword: str) -> list[TemplateMeta]:
        """按名称搜索模板"""
        all_templates = self.list_all()
        if not keyword:
            return all_templates
        kw = keyword.lower()
        return [t for t in all_templates if kw in t.name.lower()]

    # ── 内部方法 ──────────────────────────────────

    def _save_meta(self, meta: TemplateMeta):
        """序列化并保存模板元数据"""
        data = {
            "id": meta.id,
            "name": meta.name,
            "original_file": meta.original_file,
            "page_count": meta.page_count,
            "page_settings": [
                {"rotation": ps.rotation} for ps in meta.page_settings
            ],
            "fields": [
                {
                    "id": f.id,
                    "name": f.name,
                    "field_type": f.field_type,
                    "page": f.page,
                    "rect": list(f.rect),
                    "rotation": f.rotation,
                    "font_name": f.font_name,
                    "font_size": f.font_size,
                    "alignment": f.alignment,
                    "required": f.required,
                    "default_value": f.default_value,
                    "max_length": f.max_length,
                    "multiline": f.multiline,
                    "select_options": f.select_options,
                    "tab_order": f.tab_order,
                    "checked_by_default": f.checked_by_default,
                }
                for f in meta.fields
            ],
            "created_at": meta.created_at,
            "updated_at": meta.updated_at,
        }
        with open(self._json_path(meta.id), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load_meta(self, json_path: str) -> Optional[TemplateMeta]:
        """从 JSON 文件加载模板元数据"""
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError):
            return None

        meta = TemplateMeta()
        meta.id = data.get("id", meta.id)
        meta.name = data.get("name", "未命名模板")
        meta.original_file = data.get("original_file", "original.pdf")
        meta.page_count = data.get("page_count", 1)
        meta.created_at = data.get("created_at", "")
        meta.updated_at = data.get("updated_at", "")

        # 加载页面设置
        meta.page_settings = []
        for ps_data in data.get("page_settings", []):
            meta.page_settings.append(PageSettings(rotation=ps_data.get("rotation", 0.0)))
        # 补齐
        while len(meta.page_settings) < meta.page_count:
            meta.page_settings.append(PageSettings())

        # 加载字段
        meta.fields = []
        for f_data in data.get("fields", []):
            field = FieldDefinition(
                id=f_data.get("id", ""),
                name=f_data.get("name", "新字段"),
                field_type=f_data.get("field_type", "text"),
                page=f_data.get("page", 0),
                rect=tuple(f_data.get("rect", [0, 0, 100, 30])),
                rotation=f_data.get("rotation", 0.0),
                font_name=f_data.get("font_name", "china-ss"),
                font_size=f_data.get("font_size", 12.0),
                alignment=f_data.get("alignment", "left"),
                required=f_data.get("required", False),
                default_value=f_data.get("default_value", ""),
                max_length=f_data.get("max_length", 0),
                multiline=f_data.get("multiline", False),
                select_options=f_data.get("select_options", []),
                tab_order=f_data.get("tab_order", 0),
                checked_by_default=f_data.get("checked_by_default", False),
            )
            meta.fields.append(field)

        return meta

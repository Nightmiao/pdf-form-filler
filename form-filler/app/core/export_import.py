"""模板导入导出 — .lmt 文件打包/解包"""

import os
import json
import zipfile
import shutil
import tempfile
from datetime import datetime

from app.core.field_model import TemplateMeta


def export_template(
    template: TemplateMeta, template_manager, output_path: str
):
    """导出模板为 .lmt 文件（实质是 ZIP）

    Args:
        template: 模板元数据
        template_manager: TemplateManager 实例
        output_path: 输出 .lmt 文件路径
    """
    # 确保扩展名
    if not output_path.endswith(".lmt"):
        output_path += ".lmt"

    pdf_path = template_manager.get_pdf_path(template.id)
    thumb_path = template_manager.get_thumbnail_path(template.id)

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # 打包原始 PDF
        zf.write(pdf_path, "original.pdf")

        # 打包缩略图
        if os.path.exists(thumb_path):
            zf.write(thumb_path, "thumbnail.png")

        # 打包模板 JSON
        json_data = _serialize_template(template)
        zf.writestr("template.json", json.dumps(json_data, ensure_ascii=False, indent=2))


def import_template(filepath: str, template_manager) -> TemplateMeta:
    """从 .lmt 文件导入模板

    Args:
        filepath: .lmt 文件路径
        template_manager: TemplateManager 实例

    Returns:
        导入的 TemplateMeta

    Raises:
        ValueError: 文件格式不正确
        FileExistsError: 同名模板已存在（由调用方处理冲突）
    """
    if not zipfile.is_zipfile(filepath):
        raise ValueError("文件不是有效的 .lmt 模板文件")

    # 解压到临时目录
    with tempfile.TemporaryDirectory() as tmpdir:
        with zipfile.ZipFile(filepath, "r") as zf:
            zf.extractall(tmpdir)

        # 读取 template.json
        json_path = os.path.join(tmpdir, "template.json")
        if not os.path.exists(json_path):
            raise ValueError("模板文件中缺少 template.json")

        with open(json_path, "r", encoding="utf-8") as f:
            json_data = json.load(f)

        # 读取原始 PDF
        pdf_path = os.path.join(tmpdir, "original.pdf")
        if not os.path.exists(pdf_path):
            raise ValueError("模板文件中缺少原始 PDF")

        # 通过 template_manager 创建
        name = json_data.get("name", "导入的模板")
        meta = template_manager.create(name, pdf_path)

        # 覆盖字段数据
        self_dir = template_manager._template_dir(meta.id)
        _load_fields_from_json(meta, json_data)
        meta.name = name

        # 更新 page_settings
        meta.page_settings = []
        for ps_data in json_data.get("page_settings", []):
            from app.core.field_model import PageSettings
            meta.page_settings.append(PageSettings(
                rotation=ps_data.get("rotation", 0.0)
            ))
        while len(meta.page_settings) < meta.page_count:
            from app.core.field_model import PageSettings
            meta.page_settings.append(PageSettings())

        template_manager.update(meta)

        # 如果有缩略图，复制过去
        src_thumb = os.path.join(tmpdir, "thumbnail.png")
        if os.path.exists(src_thumb):
            dst_thumb = os.path.join(self_dir, "thumbnail.png")
            shutil.copy2(src_thumb, dst_thumb)

        return meta


def _serialize_template(template: TemplateMeta) -> dict:
    """序列化模板为 dict"""
    return {
        "name": template.name,
        "page_count": template.page_count,
        "page_settings": [
            {"rotation": ps.rotation} for ps in template.page_settings
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
            for f in template.fields
        ],
        "created_at": template.created_at,
        "updated_at": template.updated_at,
    }


def _load_fields_from_json(meta: TemplateMeta, json_data: dict):
    """从 JSON 数据加载字段到模板"""
    from app.core.field_model import FieldDefinition

    meta.fields = []
    for f_data in json_data.get("fields", []):
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

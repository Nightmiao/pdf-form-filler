"""模板导入导出 — .lmt 文件打包/解包（序列化复用 TemplateMeta.to_dict/from_dict）"""

from __future__ import annotations


import os
import json
import zipfile
import shutil
import tempfile

from app.core.field_model import TemplateMeta


def export_template(
    template: TemplateMeta, template_manager, output_path: str
):
    """导出模板为 .lmt 文件（实质是 ZIP）"""
    if not output_path.endswith(".lmt"):
        output_path += ".lmt"

    pdf_path = template_manager.pdf_path(template.id)
    thumb_path = template_manager.thumb_path(template.id)

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(pdf_path, "original.pdf")
        if os.path.exists(thumb_path):
            zf.write(thumb_path, "thumbnail.png")
        zf.writestr(
            "template.json",
            json.dumps(template.to_dict(), ensure_ascii=False, indent=2),
        )


def import_template(filepath: str, template_manager) -> TemplateMeta:
    """从 .lmt 文件导入模板（字段校验在 TemplateMeta.from_dict 内完成）"""
    if not zipfile.is_zipfile(filepath):
        raise ValueError("文件不是有效的 .lmt 模板文件")

    with tempfile.TemporaryDirectory() as tmpdir:
        with zipfile.ZipFile(filepath, "r") as zf:
            zf.extractall(tmpdir)

        json_path = os.path.join(tmpdir, "template.json")
        if not os.path.exists(json_path):
            raise ValueError("模板文件中缺少 template.json")

        with open(json_path, "r", encoding="utf-8") as f:
            json_data = json.load(f)

        pdf_path = os.path.join(tmpdir, "original.pdf")
        if not os.path.exists(pdf_path):
            raise ValueError("模板文件中缺少原始 PDF")

        imported = TemplateMeta.from_dict(json_data)

        # 以实际 PDF 创建新模板，再套用导入的字段/页面设置
        meta = template_manager.create(imported.name, pdf_path)
        # 页面设置与字段页码一律以实际 PDF 页数为准（口径统一，防越界）
        meta.page_settings = imported.page_settings[: meta.page_count]
        while len(meta.page_settings) < meta.page_count:
            from app.core.field_model import PageSettings
            meta.page_settings.append(PageSettings())
        meta.fields = [f for f in imported.fields if f.page < meta.page_count]
        template_manager.update(meta)

        src_thumb = os.path.join(tmpdir, "thumbnail.png")
        if os.path.exists(src_thumb):
            shutil.copy2(src_thumb, template_manager.thumb_path(meta.id))

        return meta

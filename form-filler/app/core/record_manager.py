"""填写记录管理器 — 用户填写数据的存储与读取"""

import os
import json
from datetime import datetime
from typing import Optional

from app.core.field_model import FillRecord


class RecordManager:
    """管理填写记录的生命周期"""

    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.records_dir = os.path.join(data_dir, "records")
        self._ensure_dir(self.records_dir)

    def _ensure_dir(self, path: str):
        os.makedirs(path, exist_ok=True)

    def _record_dir(self, template_id: str) -> str:
        d = os.path.join(self.records_dir, template_id)
        self._ensure_dir(d)
        return d

    def _json_path(self, template_id: str, record_id: str) -> str:
        return os.path.join(self._record_dir(template_id), f"{record_id}.json")

    def _pdf_path(self, template_id: str, record_id: str) -> str:
        return os.path.join(self._record_dir(template_id), f"{record_id}.pdf")

    # ── 记录操作 ──────────────────────────────────

    def create(self, template_id: str, name: str = "") -> FillRecord:
        """创建新填写记录"""
        record = FillRecord(template_id=template_id, name=name)
        now = datetime.now().isoformat()
        record.created_at = now
        record.updated_at = now
        return record

    def save(self, record: FillRecord):
        """保存填写记录"""
        record.updated_at = datetime.now().isoformat()
        data = {
            "id": record.id,
            "template_id": record.template_id,
            "name": record.name,
            "values": record.values,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }
        path = self._json_path(record.template_id, record.id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get(self, template_id: str, record_id: str) -> Optional[FillRecord]:
        """获取填写记录"""
        path = self._json_path(template_id, record_id)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError):
            return None

        record = FillRecord()
        record.id = data.get("id", record.id)
        record.template_id = data.get("template_id", template_id)
        record.name = data.get("name", "")
        record.values = data.get("values", {})
        record.created_at = data.get("created_at", "")
        record.updated_at = data.get("updated_at", "")
        return record

    def list_for_template(self, template_id: str) -> list[FillRecord]:
        """列出某个模板的所有填写记录"""
        records = []
        rec_dir = self._record_dir(template_id)
        if not os.path.exists(rec_dir):
            return records
        for filename in os.listdir(rec_dir):
            if filename.endswith(".json"):
                record_id = filename[:-5]  # 去掉 .json
                rec = self.get(template_id, record_id)
                if rec:
                    records.append(rec)
        records.sort(key=lambda r: r.updated_at, reverse=True)
        return records

    def delete(self, template_id: str, record_id: str):
        """删除填写记录"""
        json_path = self._json_path(template_id, record_id)
        pdf_path = self._pdf_path(template_id, record_id)
        if os.path.exists(json_path):
            os.remove(json_path)
        if os.path.exists(pdf_path):
            os.remove(pdf_path)

    def get_filled_pdf_path(self, template_id: str, record_id: str) -> str:
        """获取已导出 PDF 的路径（如果存在）"""
        path = self._pdf_path(template_id, record_id)
        if os.path.exists(path):
            return path
        return ""

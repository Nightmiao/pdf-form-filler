"""字段数据模型 — 定义表单字段和页面设置的数据结构，并提供统一的序列化/校验"""

from __future__ import annotations


from dataclasses import dataclass, field
from typing import Literal
import math
import uuid

# 字段类型
FieldType = Literal["text", "number", "date", "select", "checkbox"]
FIELD_TYPES = ("text", "number", "date", "select", "checkbox")

# 对齐方式
Alignment = Literal["left", "center", "right"]
ALIGNMENTS = ("left", "center", "right")

# 勾选框"算不算已勾选"的统一口径。
# 历史缺陷：这个集合在 6 处各写了一份，且彼此不一致 —— 导出(pdf_engine)与
# 画布显示(field_item)认 "on"，而必填校验(main_window)、填写进度与控件同步
# (field_panel) 不认。结果是同一份数据在"导出时算填了、校验时算没填"，
# 行为随入口而变。现在只保留这一个定义。
TRUTHY_VALUES = frozenset(
    {"true", "1", "yes", "on", "y", "t", "√", "✓", "是", "已勾选"}
)


def is_truthy(value) -> bool:
    """勾选框的值是否代表"已勾选"（大小写不敏感、忽略首尾空白）"""
    return str(value or "").strip().lower() in TRUTHY_VALUES


# 字号允许区间 —— 数据层与界面控件共用同一份定义。
# 历史缺陷：from_dict 限幅 4~200，而设计面板的 QDoubleSpinBox 是 6~72，
# 于是载入一个字号 100 的模板后，只要改任意一个属性，_apply_properties
# 就会把字号静默夹到 72。
MIN_FONT_SIZE = 4.0
MAX_FONT_SIZE = 200.0


def _finite(v) -> bool:
    try:
        return math.isfinite(float(v))
    except (TypeError, ValueError):
        return False


@dataclass
class PageSettings:
    """单页设置 — 用于修正扫描倾斜等"""

    rotation: float = 0.0  # 页面旋转角度（度），-5° ~ +5°

    def to_dict(self) -> dict:
        return {"rotation": self.rotation}

    @classmethod
    def from_dict(cls, data: dict) -> "PageSettings":
        rotation = data.get("rotation", 0.0)
        if not _finite(rotation):
            rotation = 0.0
        # 页面矫正角限幅，防止损坏数据导致离谱显示
        return cls(rotation=max(-15.0, min(15.0, float(rotation))))


@dataclass
class FieldDefinition:
    """表单字段定义 — 一个可填写区域的全部属性

    rect 恒为原始 PDF 坐标（页面旋转只影响显示层）。
    """

    name: str = "新字段"
    field_type: FieldType = "text"
    page: int = 0
    rect: tuple[float, float, float, float] = (0, 0, 100, 30)
    rotation: float = 0.0
    font_size: float = 12.0
    alignment: Alignment = "left"
    required: bool = False
    default_value: str = ""
    max_length: int = 0
    multiline: bool = False
    select_options: list[str] = field(default_factory=list)
    tab_order: int = 0
    checked_by_default: bool = False

    # 唯一标识，自动生成
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    @property
    def display_type(self) -> str:
        type_names = {
            "text": "文本",
            "number": "数字",
            "date": "日期",
            "select": "下拉选择",
            "checkbox": "勾选框",
        }
        return type_names.get(self.field_type, "文本")

    @property
    def width(self) -> float:
        return abs(self.rect[2] - self.rect[0])

    @property
    def height(self) -> float:
        return abs(self.rect[3] - self.rect[1])

    @property
    def center(self) -> tuple[float, float]:
        return (
            (self.rect[0] + self.rect[2]) / 2,
            (self.rect[1] + self.rect[3]) / 2,
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "field_type": self.field_type,
            "page": self.page,
            "rect": list(self.rect),
            "rotation": self.rotation,
            "font_size": self.font_size,
            "alignment": self.alignment,
            "required": self.required,
            "default_value": self.default_value,
            "max_length": self.max_length,
            "multiline": self.multiline,
            "select_options": self.select_options,
            "tab_order": self.tab_order,
            "checked_by_default": self.checked_by_default,
        }

    @classmethod
    def from_dict(cls, data: dict, page_count: int | None = None) -> "FieldDefinition | None":
        """从 JSON 数据重建字段；数据非法时返回 None（由调用方丢弃）。

        page_count 给定时校验 page 越界，越界字段直接丢弃（防止导出崩溃）。
        """
        if not isinstance(data, dict):
            return None

        rect = data.get("rect", [0, 0, 100, 30])
        if (
            not isinstance(rect, (list, tuple))
            or len(rect) != 4
            or not all(_finite(v) for v in rect)
        ):
            return None

        page = data.get("page", 0)
        try:
            page = int(page)
        except (TypeError, ValueError):
            page = 0
        if page_count is not None and not (0 <= page < page_count):
            return None
        if page < 0:
            page = 0

        field_type = data.get("field_type", "text")
        if field_type not in FIELD_TYPES:
            field_type = "text"
        alignment = data.get("alignment", "left")
        if alignment not in ALIGNMENTS:
            alignment = "left"

        font_size = data.get("font_size", 12.0)
        if not _finite(font_size):
            font_size = 12.0
        font_size = max(MIN_FONT_SIZE, min(MAX_FONT_SIZE, float(font_size)))

        rotation = data.get("rotation", 0.0)
        if not _finite(rotation):
            rotation = 0.0

        max_length = data.get("max_length", 0)
        try:
            max_length = max(0, min(9999, int(max_length)))
        except (TypeError, ValueError):
            max_length = 0

        tab_order = data.get("tab_order", 0)
        try:
            tab_order = max(0, int(tab_order))
        except (TypeError, ValueError):
            tab_order = 0

        select_options = data.get("select_options", [])
        if not isinstance(select_options, list):
            select_options = []
        select_options = [str(o) for o in select_options][:200]

        return cls(
            id=str(data.get("id") or uuid.uuid4().hex[:12]),
            name=str(data.get("name") or "新字段"),
            field_type=field_type,
            page=page,
            rect=(float(rect[0]), float(rect[1]), float(rect[2]), float(rect[3])),
            rotation=float(rotation),
            font_size=font_size,
            alignment=alignment,
            required=bool(data.get("required", False)),
            default_value=str(data.get("default_value") or ""),
            max_length=max_length,
            multiline=bool(data.get("multiline", False)),
            select_options=select_options,
            tab_order=tab_order,
            checked_by_default=bool(data.get("checked_by_default", False)),
        )


@dataclass
class TemplateMeta:
    """模板元数据"""

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    name: str = "未命名模板"
    original_file: str = "original.pdf"
    page_count: int = 1
    page_settings: list[PageSettings] = field(default_factory=list)
    fields: list[FieldDefinition] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        if not self.page_settings:
            self.page_settings = [PageSettings() for _ in range(self.page_count)]
        while len(self.page_settings) < self.page_count:
            self.page_settings.append(PageSettings())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "original_file": self.original_file,
            "page_count": self.page_count,
            "page_settings": [ps.to_dict() for ps in self.page_settings],
            "fields": [f.to_dict() for f in self.fields],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TemplateMeta":
        """从 JSON 重建模板；字段数据在此统一校验与清洗"""
        meta = cls()
        meta.id = str(data.get("id") or meta.id)
        meta.name = str(data.get("name") or "未命名模板")
        meta.original_file = str(data.get("original_file") or "original.pdf")
        try:
            meta.page_count = max(1, int(data.get("page_count", 1)))
        except (TypeError, ValueError):
            meta.page_count = 1
        meta.created_at = str(data.get("created_at") or "")
        meta.updated_at = str(data.get("updated_at") or "")

        meta.page_settings = [
            PageSettings.from_dict(d)
            for d in data.get("page_settings", [])
            if isinstance(d, dict)
        ]
        while len(meta.page_settings) < meta.page_count:
            meta.page_settings.append(PageSettings())

        meta.fields = []
        for f_data in data.get("fields", []):
            f = FieldDefinition.from_dict(f_data, page_count=meta.page_count)
            if f is not None:
                meta.fields.append(f)
        return meta


@dataclass
class FillRecord:
    """填写记录"""

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    template_id: str = ""
    name: str = ""
    values: dict[str, str] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""
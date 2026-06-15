"""字段数据模型 — 定义表单字段和页面设置的数据结构"""

from dataclasses import dataclass, field
from typing import Literal
import uuid

# 字段类型
FieldType = Literal["text", "number", "date", "select", "checkbox"]

# 对齐方式
Alignment = Literal["left", "center", "right"]


@dataclass
class PageSettings:
    """单页设置 — 用于修正扫描倾斜等"""

    rotation: float = 0.0  # 页面旋转角度（度），-5° ~ +5°


@dataclass
class FieldDefinition:
    """表单字段定义 — 一个可填写区域的全部属性"""

    name: str = "新字段"  # 字段名称，如"姓名"
    field_type: FieldType = "text"  # 字段类型
    page: int = 0  # 所在页码（0-based）
    rect: tuple[float, float, float, float] = (0, 0, 100, 30)  # PDF坐标 (x0, y0, x1, y1) in points
    rotation: float = 0.0  # 字段自身旋转角度（度）
    font_name: str = "china-ss"  # 字体名称（PyMuPDF内置中文: china-s, china-ss）
    font_size: float = 12.0  # 字号
    alignment: Alignment = "left"  # 对齐方式
    required: bool = False  # 是否必填
    default_value: str = ""  # 默认值
    max_length: int = 0  # 最大字符数（0=不限制）
    multiline: bool = False  # 是否多行文本
    select_options: list[str] = field(default_factory=list)  # 下拉选项
    tab_order: int = 0  # TAB 跳转顺序
    checked_by_default: bool = False  # 勾选框默认是否选中

    # 唯一标识，自动生成
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    @property
    def display_type(self) -> str:
        """返回类型的中文显示名"""
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
        return self.rect[2] - self.rect[0]

    @property
    def height(self) -> float:
        return self.rect[3] - self.rect[1]


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
        # 确保 page_settings 与 page_count 一致
        while len(self.page_settings) < self.page_count:
            self.page_settings.append(PageSettings())


@dataclass
class FillRecord:
    """填写记录"""

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    template_id: str = ""
    name: str = ""
    values: dict[str, str] = field(default_factory=dict)  # field_id → 填写的值
    created_at: str = ""
    updated_at: str = ""

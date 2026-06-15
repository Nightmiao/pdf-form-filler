# 狸猫猫的表单填写工具

一款纯前端的 Python 桌面应用，帮助用户为 PDF 表单标记可填写字段，并通过 TAB 快速填写、保存和打印。

## 功能

- 📄 **上传 PDF 表单** — 支持多页 PDF
- ✏️ **低代码设计模式** — 拖拽画框标记可填写区域
- 🔧 **丰富字段类型** — 文本、数字、日期、下拉选择、勾选框
- 📐 **对齐辅助** — 网格吸附 + 对齐线
- 🔄 **旋转支持** — 修正扫描倾斜（页面旋转）+ 字段旋转
- ⌨️ **TAB 快速填写** — 键盘高效填写表单
- 💾 **本地存储** — 模板和记录保存在本地
- 🖨️ **打印 & 导出 PDF** — 烧录填写内容到 PDF
- 📦 **模板导入/导出** — .lmt 格式打包分享

## 快捷键与鼠标操作

### 鼠标
- **右键拖动** — 平移画布
- **右键单击字段** — 弹出菜单（设计模式）
- **滚轮** — 缩放画布
- **Shift+滚轮** — 翻页
- **中键拖动** — 平移画布（备用）

### 键盘
| 快捷键 | 功能 |
| --- | --- |
| `Ctrl` `+` / `-` | 放大 / 缩小 |
| `Ctrl` `0` | 适应窗口 |
| `Ctrl` `1` | 实际比例（1:1） |
| `PageUp` / `PageDown` | 上一页 / 下一页 |
| `方向键` | 微移选中字段（1pt） |
| `Shift`+`方向键` | 微移选中字段（10pt） |
| `Ctrl` `C` / `V` | 复制 / 粘贴字段 |
| `Ctrl` `D` | 原地复制字段 |
| `Delete` | 删除选中字段 |
| `Esc` | 取消画框 / 取消选中 |
| `Tab` | 填写模式下跳到下一字段 |
| `Ctrl` `S` | 保存 |

## 安装

```bash
# 创建虚拟环境
python -m venv venv
source venv/Scripts/activate  # Windows
# 或 source venv/bin/activate  # Mac/Linux

# 安装依赖
pip install -r requirements.txt
```

## 运行

```bash
python main.py
```

## 打包为 EXE

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name="狸猫猫的表单填写工具" main.py
```

## 项目结构

```
form-filler/
├── main.py                    # 程序入口
├── requirements.txt
├── app/
│   ├── ui/                    # UI 层
│   │   ├── main_window.py     # 主窗口
│   │   ├── home_page.py       # 首页（模板管理）
│   │   ├── design_mode.py     # 设计模式
│   │   ├── fill_mode.py       # 填写模式
│   │   ├── pdf_canvas.py      # PDF 画布
│   │   ├── field_panel.py     # 属性/填写面板
│   │   ├── field_item.py      # 可拖拽字段图元
│   │   ├── thumbnail_bar.py   # 缩略图导航
│   │   ├── alignment_overlay.py  # 对齐辅助
│   │   ├── preview_dialog.py  # 预览对话框
│   │   └── print_helper.py    # 打印辅助
│   └── core/                  # 核心引擎层
│       ├── pdf_engine.py      # PDF 读写渲染
│       ├── template_manager.py # 模板 CRUD
│       ├── record_manager.py  # 填写记录 CRUD
│       ├── field_model.py     # 数据模型
│       └── export_import.py   # .lmt 导入导出
└── data/                      # 用户数据目录（~/.form-filler/）
```

## 技术栈

- **GUI**: PySide6
- **PDF 引擎**: PyMuPDF (fitz)
- **存储**: JSON 文件
- **打包**: PyInstaller

# 狸猫猫表单

一款纯本地的中文桌面应用：给 PDF 表单画好填写框，之后就能像填写电子表单一样快速填写、保存草稿、导出 PDF 或直接打印。原始 PDF 文件永远不会被改动。

## 三步工作流

1. **新建模板** — 在首页点击「新建模板」，选择一张 PDF 表单；
2. **设计字段** — 按住鼠标左键在表格空白处拖拽画框，在右侧设置名称、类型（文本/数字/日期/下拉选择/勾选框）、字号、对齐、是否必填等；
3. **填写导出** — 点击「去填写」，按 Tab 依次填写（或直接点 PDF 上的蓝色框），保存草稿、预览、导出 PDF 或打印。

首次打开软件会有 3 步图文引导；首页的「使用说明」可随时再次查看。

## 功能

- 模板库首页 — 带 PDF 缩略图的卡片墙、搜索、重命名、导入/导出（.lmt 格式，可分享给同事）
- 可视化字段设计 — 拖拽画框、移动、缩放、旋转字段；网格吸附 + 对齐辅助线；撤销/重做（Ctrl+Z / Ctrl+Y）
- 页面旋转矫正 — 给扫描歪斜的表格掰正（-5° ~ +5°），矫正角一并写入导出文件，显示与导出完全一致
- 任意角度字段旋转 — 导出用 morph 矩阵精确写入，不再四舍五入到 90°
- 多份填写记录 — 同一张表单可以保存多份记录（例如给不同的人各填一份），可新建、重命名、切换、删除
- 必填校验 — 导出/打印前提示漏填的必填项，并可一键跳转到漏填处
- 预览 / 导出 / 打印 — 填写内容烧录进 PDF；打印自动适应纸张大小
- 键盘高效操作 — Tab 跨页跳转、Ctrl+S 保存等（见下表）
- 大文件不卡顿 — 缩略图后台异步渲染，画布相邻页预取 + 像素缓存 LRU，搜索输入防抖

## 鼠标与键盘操作

| 操作 | 方式 |
| --- | --- |
| 画字段框 | 设计模式：按住鼠标左键在空白处拖拽 |
| 移动 / 缩放 / 旋转字段 | 拖动框体 / 拖四角小圆点 / 拖顶部橙色圆点（Shift=15° 步进） |
| 平移画布 | 右键拖动、中键拖动，或按住空格 + 左键拖动 |
| 缩放 | Ctrl+滚轮，或 Ctrl + / -；Ctrl+0 适应窗口；Ctrl+1 实际大小 |
| 滚动页面 | 滚轮（页面放大超出视口时上下滚动，与 PDF 阅读器一致） |
| 翻页 | PageUp / PageDown，Shift+滚轮，或点左侧缩略图 |
| 微移字段 | 方向键（1pt），Shift+方向键（10pt） |
| 复制 / 粘贴 / 原地复制 | Ctrl+C / Ctrl+V / Ctrl+D |
| 删除字段 | Delete（或右键菜单） |
| 撤销 / 重做 | Ctrl+Z / Ctrl+Y |
| 保存 | Ctrl+S（设计模式存模板，填写模式存草稿） |
| 打印 | Ctrl+P（填写模式） |
| 依次填写 | Tab 下一个，Shift+Tab 上一个（自动跨页；多行文本框内 Ctrl+Tab 插入制表符） |

## 安装与运行

需要 Python 3.10+（Windows / macOS / Linux 均可）：

    # 1. 创建虚拟环境并安装依赖
    python -m venv venv
    venv\Scripts\activate        # Windows；macOS/Linux 用 source venv/bin/activate
    pip install -r requirements.txt

    # 2. 运行
    python main.py

用户数据（模板、填写记录）保存在用户目录的 .form-filler/data 下。

### 启动方式（Windows 推荐第 1 种）

1. **双击项目根目录的 `run_app.bat`** —— 自动使用项目自带的 `venv`，无需手动激活；
   若双击没反应，项目根目录会生成 `run_app.log` 记录启动过程（便于排查）；
2. 命令行启动（注意要用 venv 里的 Python）：

       venv\Scripts\python.exe main.py

3. 打包后的 EXE：`dist` 目录下的可执行文件。

> ⚠️ 不要用 `py main.py` 或系统里的 `python main.py`：依赖（PySide6 等）装在项目内的
> `venv` 目录里，系统 Python 没有这些包，会报 `ModuleNotFoundError: No module named 'PySide6'`。

## 自动化测试

离屏自动化测试共四套，两套环境（开发机 PySide6/Qt6 与 Win7 兼容环境
Python 3.8/3.9 + PySide2/Qt5）都必须全绿：

    venv\Scripts\python.exe tests\smoke_test.py         # 全流程冒烟/回归 + 界面截图
    venv\Scripts\python.exe tests\audit_verify.py       # 旋转几何 / 并发 / 句柄审计
    venv\Scripts\python.exe tests\print_accuracy.py     # 打印落点精度（需要打印机）
    venv\Scripts\python.exe tests\ui_layout_check.py    # 1024x768 小屏布局 + Win7 字体安全

覆盖点：建模板 → 画字段 → 页面旋转精确换算 → 撤销/重做 → 排序同步 → 跨页 Tab →
填写/保存 → 烧录校验（含 15° 任意角度与页面矫正角导出）→ 记录切换持久化 →
非法字段防御 → 导出路径防覆盖 → 预览异常保护 → 缩略图异步渲染 → LRU 缓存 →
搜索防抖 → 必填校验 → **打印落点误差 < 0.4mm** → **1024x768 下关键按钮不被溢出菜单吞掉**。

> **tests/print_accuracy.py 为什么重要**：早期版本把 `QPrinter.pageRect()` 的
> 页边距当成画笔偏移量叠加，导致整页内容向右下平移一个页边距（A4 实测 3.5mm），
> 右下角还会被裁掉。旧用例只检查"页面上有没有暗像素"，位移 10pt 也能通过，
> 所以这个缺陷躲过了好几轮回归。新用例用两个已知位置的基准方块反算实际落点，
> 误差超过 0.42mm 直接失败。

## 打包为 EXE（Windows）

    pip install pyinstaller
    pyinstaller --onefile --windowed --name="狸猫猫表单" main.py

仓库还提供了 build_msi.bat（生成 MSI 安装包，需要 WiX Toolset）。

## Windows 7 / 离线部署（重要）

最终目标机是**离线（无网络）的 Windows 7**。Python 3.10+ 与 Qt 6 官方均不支持 Win7，
因此项目做了双环境适配，完整说明见 **docs/Windows7-离线部署.md**。要点：

- 代码通过 **app/qt.py 兼容层**自动适配：开发机用 PySide6（Qt 6），Win7 目标机用
  **Python 3.9 + PySide2 5.15（Qt 5）+ PyMuPDF 1.23**，同一份源码无需改动；
- 离线依赖 wheel 已备好在 **vendor/wheels/**（64 位），构建机双击 **build_win7.bat**
  一键产出绿色 EXE，拷到 Win7 双击即用，目标机无需安装 Python；
- Win7 系统要求：SP1 + VC++ 2015-2019 运行库（精简版系统另需 KB2533623 / KB2999226 补丁），
  详见文档的常见问题清单。

### 打印出问题时怎么办：内置自检

程序带一个自检模式，会把运行环境、字体、打印机列表和**打印坐标**写成一份报告：

    狸猫猫表单.exe --diagnose        （命令行）
    或在快捷方式的目标后面加 --diagnose

报告写到桌面：**狸猫猫表单-自检报告.txt**。打印不正常时把这份文件发给开发者即可定位。

### Win7 上的界面适配

- **DPI 感知**：程序启动时声明 DPI 感知，125% 缩放下界面不会被系统拉伸模糊、
  右侧面板也不会跑到屏幕外；
- **小屏自适应**：窗口按屏幕可用区域决定初始大小；低于 1180px 宽时左侧缩略图栏
  自动收起（状态栏右下角「显示缩略图」或 Ctrl+B 可随时开关），
  保证「保存」「去填写」「调整设计」这些关键按钮在 1024x768 上也直接可见、不进溢出菜单；
- **不依赖 emoji 字体**：Win7 没有彩色 emoji（Segoe UI Emoji 从 Win8 才有），
  界面上所有图标都用 QPainter 自绘或 Qt 内置标准图标，不会出现空心方框。

## 项目结构

    form-filler/
    ├── main.py                    # 程序入口（DPI 感知/主题/窗口尺寸/--diagnose）
    ├── requirements.txt
    ├── app/
    │   ├── qt.py                  # Qt5/Qt6 兼容层（唯一允许碰 PySide 的地方）
    │   ├── version.py             # 版本号与构建日期
    │   ├── ui/                    # 界面层
    │   │   ├── main_window.py     # 主窗口（模式切换/记录管理/必填校验/窄屏自适应）
    │   │   ├── home_page.py       # 首页模板库（卡片墙/搜索/空状态/自检入口）
    │   │   ├── design_mode.py     # 设计模式（两级工具栏）
    │   │   ├── fill_mode.py       # 填写模式
    │   │   ├── pdf_canvas.py      # PDF 画布（渲染/交互/撤销重做/旋转换算）
    │   │   ├── field_item.py      # 可拖拽字段图元
    │   │   ├── field_panel.py     # 右侧面板（设计属性 / 填写输入+记录管理）
    │   │   ├── thumbnail_bar.py   # 缩略图导航
    │   │   ├── alignment_overlay.py  # 网格吸附与对齐线
    │   │   ├── preview_dialog.py  # 预览弹窗（可导出/打印）
    │   │   ├── print_helper.py    # 打印（坐标换算见文件头注释）
    │   │   ├── onboarding.py      # 3 步新手引导
    │   │   └── theme.py           # 全局样式表 + 自绘图标 + 省略号标签
    │   └── core/                  # 核心层
    │       ├── pdf_engine.py      # PDF 渲染/烧录/旋转几何
    │       ├── template_manager.py
    │       ├── record_manager.py  # 多份填写记录管理
    │       ├── field_model.py     # 数据模型
    │       ├── export_import.py   # .lmt 导入导出
    │       ├── diagnostics.py     # 运行自检（环境/字体/打印机/打印落点）
    │       └── settings.py        # 应用设置
    └── tests/
        ├── smoke_test.py          # 全流程冒烟 + 界面截图
        ├── audit_verify.py        # 旋转几何/并发/句柄审计
        ├── print_accuracy.py      # 打印落点精度（真实打印管线）
        └── ui_layout_check.py     # 小屏布局 + Win7 字体安全

## 技术栈

- GUI：PySide6 (Qt 6，开发机) / PySide2 (Qt 5，Windows 7 目标机，经 app/qt.py 兼容层适配)
- PDF 引擎：PyMuPDF (fitz)
- 存储：本地 JSON 文件
- 打包：PyInstaller / MSI
- 依赖：requirements.txt 锁定本机实测版本
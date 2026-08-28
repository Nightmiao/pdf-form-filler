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
| 依次填写 | Tab 下一个，Shift+Tab 上一个（自动跨页） |

## 安装与运行

需要 Python 3.10+（Windows / macOS / Linux 均可）：

    # 1. 创建虚拟环境并安装依赖
    python -m venv venv
    venv\Scripts\activate        # Windows；macOS/Linux 用 source venv/bin/activate
    pip install -r requirements.txt

    # 2. 运行
    python main.py

用户数据（模板、填写记录）保存在用户目录的 .form-filler/data 下。

## 自动化测试

离屏冒烟/回归测试覆盖：建模板 → 画字段 → 页面旋转精确换算 → 撤销/重做 → 排序同步 → 跨页 Tab → 填写/保存 → 烧录校验（含 15° 任意角度与页面矫正角导出）→ 记录切换持久化 → 非法字段防御 → 导出路径防覆盖 → 预览异常保护 → 缩略图异步渲染 → LRU 缓存 → 搜索防抖 → 必填校验，并输出各界面截图：

    venv\Scripts\python.exe tests\smoke_test.py
    venv\Scripts\python.exe tests\audit_verify.py

两套环境均已验证通过：开发机（PySide6/Qt6）与 Windows 7 兼容环境
（Python 3.8/3.9 + PySide2/Qt5，可用 build_win7.bat 或离线 wheel 搭建）。

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

## 项目结构

    form-filler/
    ├── main.py                    # 程序入口（应用主题/字体/启动）
    ├── requirements.txt
    ├── app/
    │   ├── ui/                    # 界面层
    │   │   ├── main_window.py     # 主窗口（模式切换/记录管理/必填校验）
    │   │   ├── home_page.py       # 首页模板库（卡片墙/搜索/空状态）
    │   │   ├── design_mode.py     # 设计模式（两级工具栏）
    │   │   ├── fill_mode.py       # 填写模式
    │   │   ├── pdf_canvas.py      # PDF 画布（渲染/交互/撤销重做/旋转换算）
    │   │   ├── field_item.py      # 可拖拽字段图元
    │   │   ├── field_panel.py     # 右侧面板（设计属性 / 填写输入+记录管理）
    │   │   ├── thumbnail_bar.py   # 缩略图导航
    │   │   ├── alignment_overlay.py  # 网格吸附与对齐线
    │   │   ├── preview_dialog.py  # 预览弹窗（可导出/打印）
    │   │   ├── print_helper.py    # 打印（自适应纸张）
    │   │   ├── onboarding.py      # 3 步新手引导
    │   │   └── theme.py           # 全局浅色主题与样式表
    │   └── core/                  # 核心层
    │       ├── pdf_engine.py      # PDF 渲染/烧录/旋转几何
    │       ├── template_manager.py
    │       ├── record_manager.py  # 多份填写记录管理
    │       ├── field_model.py     # 数据模型
    │       ├── export_import.py   # .lmt 导入导出
    │       └── settings.py        # 应用设置
    └── tests/
        └── smoke_test.py          # 离屏自动化冒烟测试

## 技术栈

- GUI：PySide6 (Qt 6，开发机) / PySide2 (Qt 5，Windows 7 目标机，经 app/qt.py 兼容层适配)
- PDF 引擎：PyMuPDF (fitz)
- 存储：本地 JSON 文件
- 打包：PyInstaller / MSI
- 依赖：requirements.txt 锁定本机实测版本
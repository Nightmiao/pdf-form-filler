# Windows 7 离线部署指南

本应用最终运行环境是**离线（无网络）的 Windows 7 电脑**。由于 Python 3.10+ 和 Qt 6 官方都不再支持 Windows 7，本项目做了以下适配，请按本指南部署。

## 一、技术适配说明（为什么这样设计）

| 组件 | 开发机（当前环境） | Windows 7 目标机 |
| --- | --- | --- |
| Python | 3.13 | **3.9.13**（最后一个支持 Win7 的大版本） |
| Qt 框架 | PySide6（Qt 6） | **PySide2 5.15.2.1（Qt 5）** |
| PDF 引擎 | PyMuPDF 1.27 | **PyMuPDF 1.23.26** |

代码通过 app/qt.py 兼容层自动适配两套环境：**同一份源码，开发机上用 PySide6 开发测试，目标机上跑 PySide2 版本，不需要改任何代码**。全部界面代码都从 app.qt 导入 Qt 类，不直接 import PySide6/PySide2。

> **验证状态**：本仓库已在 **Python 3.8 + PySide2 5.15.2.1 + PyMuPDF 1.23.26** 环境完整跑通全部回归测试
> （tests/smoke_test.py 与 tests/audit_verify.py，Qt5 分支真实验证），开发机 PySide6 环境同样全绿。
> 目标机锁定 Python 3.9.13（与 3.8 行为一致）。

## 二、目标机（Windows 7）系统要求

- Windows 7 **SP1**，32 位或 64 位均可；
- **VC++ 2015-2019 运行库**（x64/x86），微软官方离线安装包：
  https://aka.ms/vs/17/release/vc_redist.x64.exe（多数 Win7 已自带，报缺 dll 再装）；
- 精简版系统（GHOST 版等）可能还缺两个补丁：
  - KB2533623（API Set）
  - KB2999226（UCRT，报 "api-ms-win-crt-..." 错误时装）
- 中文显示无需额外字体：Win7 自带微软雅黑（msyh.ttc）和宋体（simsun.ttc）。

## 三、发布前真机抽验清单（必做）

离屏回归测试无法覆盖真机的字体渲染、打印驱动与高 DPI，分发前请在 Win7 真机（或干净虚拟机）完整走一遍：

1. 双击 EXE 启动 → 首次出现 3 步新手引导，完成后进入首页；
2. 「新建模板」选一张多页 PDF → 设计模式：拖拽画 2-3 个字段框，设一个勾选框、一个必填项，调一下页面旋转矫正滑杆；
3. 「去填写」→ 按 Tab 依次填写、点画布蓝框直接定位输入、保存草稿、新建第二份记录并切换回来确认内容都在；
4. 「预览」放大缩小 → 「导出 PDF」到桌面，用任意阅读器打开核对：中文显示正常、勾选框是 √、旋转字段方向与画布一致；
5. 「打印」到一台真实打印机（或虚拟 PDF 打印机），确认纸张适配与内容完整。
   **重点核对**：打印出来的表格边缘（尤其右下角）没有被切掉、内容没有整体偏移。
   程序按"等比缩放居中铺满可打印区"输出，正常情况下四边留白对称。

以上 5 步全部通过后，再把 EXE 分发给使用者。

### 打印/显示异常时的第一步：跑一次自检

程序内置自检模式，会生成一份报告（桌面上的 `狸猫猫表单-自检报告.txt`）：

    狸猫猫表单.exe --diagnose

报告包含：Python/Qt/PyMuPDF 版本、屏幕分辨率与 DPI、中文字体是否存在、
已安装打印机列表、默认打印机、以及**可打印区与画笔坐标系的实测值**。
打印不正常时先把这份报告发出来，能省掉大半排查时间。

## 三之二、已修复的历史缺陷（供排查参考）

| 现象 | 根因 | 现状 |
| --- | --- | --- |
| 打印出来整页空白 | 按打印机 DPI（600/1200）渲染整页位图，尺寸近万像素、数百 MB，QImage 加载失败 | 渲染分辨率封顶 300 DPI，失败自动降级 150 DPI |
| **打印内容整体向右下偏移、右下角被切掉** | `QPrinter.pageRect()` 的页边距被当成画笔偏移量叠加，而 QPainter 在打印机上的原点**本来就是可打印区左上角** | 改用 `painter.window()`（画笔自己的逻辑页面）做居中，实测落点误差 < 0.4mm；见 `tests/print_accuracy.py` |
| 点了「打印」什么都不发生 | 打印过程抛异常时无控制台可看，异常直接消失在 Qt 槽里 | 整个打印流程包了异常兜底，任何失败都会弹提示框说明原因 |
| 多页表单打印时界面像卡死 | 整页 300 DPI 渲染期间不处理事件 | 每页之间 `processEvents()` + 等待光标 |
| 125% 缩放下右侧面板跑到屏幕外 | 程序没有声明 DPI 感知，系统把界面虚拟化放大 | 启动时声明 DPI 感知；窗口按屏幕可用区域推导；最小尺寸降到 940x600 |
| 1024x768 上找不到「保存」「去填写」 | 左栏 208 + 右栏 300 只剩 516px，工具栏按钮被塞进 "»" 溢出菜单 | 窄屏自动收起缩略图栏（Ctrl+B 可开），主操作移到工具栏最右端，实测 1024x680 下零溢出 |
| 首页空状态是个空心方框 | 界面用了 emoji（Win7 没有 Segoe UI Emoji 字体） | 所有图标改为 QPainter 自绘 / Qt 内置标准图标 |
| 白色卡片/工具栏里出现灰色方块 | 全局 `QWidget{background}` 传染给了 QLabel | 样式表加 `QLabel{background:transparent}` |


## 四、部署方案 A（推荐）：离线安装包 / 绿色便携 EXE

**方式一（最简单）：离线安装包** `dist-win7/狸猫猫表单离线安装包.exe`
把这一个文件拷到 Win7 电脑，**双击即完成安装**：程序自动解压到
`%LOCALAPPDATA%\狸猫猫表单`、在桌面创建快捷方式，并询问是否立即启动。
卸载：安装目录里的「卸载.bat」，或直接删除该目录和桌面快捷方式。

**方式二：绿色便携 EXE** `dist-win7/狸猫猫表单.exe`
单文件、免安装，拷到任意目录双击即可运行（无快捷方式）。

> 两个 EXE 都是 Python 3.8 + PySide2(Qt5) 构建的 Win7 兼容版；
> 在有网的构建机上运行 build_installer.bat 可一键重建两者。


目标机**无需安装 Python**，双击即用。

1. 找一台**联网**的电脑（Win10/11 均可），安装 **Python 3.9.13（64 位）**：
   https://www.python.org/downloads/release/python-3913/
2. 把本项目整个文件夹拷过去，双击运行 **build_win7.bat**；
   （依赖优先从离线目录 vendor/wheels 安装，没网也能构建）
3. 构建完成后，把 dist 目录下的"狸猫猫表单.exe"拷贝到 Win7 机器，双击运行。

> 若 Win7 是 32 位系统：需要 32 位 Python 3.9 + 32 位 wheel（vendor 里的 wheel 是 64 位的，
> 在联网机构建机上执行 pip download 时把 --platform win_amd64 换成 --platform win32 重新下载即可）。

## 五、部署方案 B：源码离线运行（便于二次开发）

1. 在联网电脑上确认 vendor/wheels 已包含全部离线依赖（本仓库已备好 64 位包）；
2. 拷贝三样东西到 Win7 机器：
   - Python 3.9.13 安装包（python.org 下载，先装好）
   - 本项目文件夹（含 vendor/wheels）
3. 在项目目录执行（全程无网络）：

    python -m venv venv
    venv\Scripts\pip install --no-index --find-links vendor\wheels -r requirements-win7.txt
    venv\Scripts\python main.py

## 六、离线依赖如何补充/更新

在有网机器上执行（64 位示例）：

    pip download -r requirements-win7.txt -d vendor/wheels --only-binary=:all: --platform win_amd64 --python-version 39 --implementation cp --abi cp39
    pip download -d vendor/wheels --only-binary=:all: --platform win_amd64 --python-version 39 --implementation cp --abi cp39 pyinstaller==5.13.2 pyinstaller-hooks-contrib==2023.7

## 七、数据与备份

- 用户数据目录：%USERPROFILE%\.form-filler\data（模板、填写记录、设置）
- **迁移/备份方法**：直接拷贝上面这个目录即可，换电脑后原样放回即可恢复。

## 八、常见问题

| 现象 | 原因与处理 |
| --- | --- |
| 报 "api-ms-win-crt-runtime..." 缺失 | 装 KB2999226（UCRT）或 VC++ 2015-2019 运行库 |
| 报 "不是有效的 Win32 应用程序" | 64 位 EXE 跑到了 32 位系统上，改用 32 位构建 |
| 双击无反应 | 先装 VC++ 运行库；用 onedir 模式打包排查依赖 |
| 杀毒软件误报 | 单文件 EXE 常见误报，添加白名单；或改用 onedir 目录版 |
| 导出的 PDF 中文乱码/空白 | 检查 C:\Windows\Fonts\simsun.ttc 是否存在（精简系统可能被删） |
| 双击 .bat 弹出"Windows 找不到 '\l'"之类的怪错误 | 批处理文件的编码问题：Win7 的 cmd 对 **UTF-8 + chcp 65001** 的批处理有解析缺陷，会把中文行拆成乱码命令。本项目约定：**.bat 一律用 GBK+chcp 936，或纯 ASCII（如 run_app.bat）**，不要再混用 UTF-8 |
| 启动脚本没反应 | 查看项目根目录的 `run_app.log`（一键启动脚本会记录启动过程） |

## 九、版本锁定清单

- Python 3.9.13
- PySide2 == 5.15.2.1（依赖 shiboken2 == 5.15.2.1）
- PyMuPDF == 1.23.26
- PyInstaller == 5.13.2（构建机用）
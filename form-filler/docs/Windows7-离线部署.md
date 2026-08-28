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

## 三、部署方案 A（推荐）：绿色便携 EXE

目标机**无需安装 Python**，双击即用。

1. 找一台**联网**的电脑（Win10/11 均可），安装 **Python 3.9.13（64 位）**：
   https://www.python.org/downloads/release/python-3913/
2. 把本项目整个文件夹拷过去，双击运行 **build_win7.bat**；
   （依赖优先从离线目录 vendor/wheels 安装，没网也能构建）
3. 构建完成后，把 dist 目录下的"狸猫猫表单.exe"拷贝到 Win7 机器，双击运行。

> 若 Win7 是 32 位系统：需要 32 位 Python 3.9 + 32 位 wheel（vendor 里的 wheel 是 64 位的，
> 在联网机构建机上执行 pip download 时把 --platform win_amd64 换成 --platform win32 重新下载即可）。

## 四、部署方案 B：源码离线运行（便于二次开发）

1. 在联网电脑上确认 vendor/wheels 已包含全部离线依赖（本仓库已备好 64 位包）；
2. 拷贝三样东西到 Win7 机器：
   - Python 3.9.13 安装包（python.org 下载，先装好）
   - 本项目文件夹（含 vendor/wheels）
3. 在项目目录执行（全程无网络）：

    python -m venv venv
    venv\Scripts\pip install --no-index --find-links vendor\wheels -r requirements-win7.txt
    venv\Scripts\python main.py

## 五、离线依赖如何补充/更新

在有网机器上执行（64 位示例）：

    pip download -r requirements-win7.txt -d vendor/wheels --only-binary=:all: --platform win_amd64 --python-version 39 --implementation cp --abi cp39
    pip download -d vendor/wheels --only-binary=:all: --platform win_amd64 --python-version 39 --implementation cp --abi cp39 pyinstaller==5.13.2 pyinstaller-hooks-contrib==2023.7

## 六、数据与备份

- 用户数据目录：%USERPROFILE%\.form-filler\data（模板、填写记录、设置）
- **迁移/备份方法**：直接拷贝上面这个目录即可，换电脑后原样放回即可恢复。

## 七、常见问题

| 现象 | 原因与处理 |
| --- | --- |
| 报 "api-ms-win-crt-runtime..." 缺失 | 装 KB2999226（UCRT）或 VC++ 2015-2019 运行库 |
| 报 "不是有效的 Win32 应用程序" | 64 位 EXE 跑到了 32 位系统上，改用 32 位构建 |
| 双击无反应 | 先装 VC++ 运行库；用 onedir 模式打包排查依赖 |
| 杀毒软件误报 | 单文件 EXE 常见误报，添加白名单；或改用 onedir 目录版 |
| 导出的 PDF 中文乱码/空白 | 检查 C:\Windows\Fonts\simsun.ttc 是否存在（精简系统可能被删） |

## 八、版本锁定清单

- Python 3.9.13
- PySide2 == 5.15.2.1（依赖 shiboken2 == 5.15.2.1）
- PyMuPDF == 1.23.26
- PyInstaller == 5.13.2（构建机用）
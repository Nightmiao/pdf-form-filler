"""本地存储的公共保障 —— id 消毒 + 原子写入

两个问题都是"平时看不出来、出事就很难查"的类型：

1) **id 会拼进文件路径**。模板 id / 记录 id 都取自 JSON 内容（template.json /
   `<record>.json`），随后直接用于 `os.path.join`、`os.remove`、`shutil.rmtree`。
   一份被手工篡改或来自不可信来源的 JSON，只要把 id 写成 `../../x`，删除/写入
   就能打到数据目录之外。这里统一校验：只允许 `[A-Za-z0-9_-]{1,64}`。

2) **写入不是原子的**。原实现是 `open(path, "w")` 直接写 —— 一旦断电、磁盘满或
   进程被杀，就会留下半截 JSON；而 `_load_meta` / `get` 对坏 JSON 是**静默**
   返回 None，用户看到的是"模板/记录凭空消失"（文件和 PDF 其实还在磁盘上）。
   改为"同目录临时文件 + fsync + os.replace"，替换是原子的，读到的永远是
   完整的旧版本或完整的新版本。
"""

from __future__ import annotations


import json
import os
import re
import tempfile

_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class UnsafeIdError(ValueError):
    """id 含路径分隔符、相对路径等危险字符"""


def is_safe_id(value) -> bool:
    return bool(_SAFE_ID_RE.match(str(value or "")))


def safe_id(value) -> str:
    """校验并返回合法 id；非法则抛 UnsafeIdError"""
    text = str(value or "")
    if not _SAFE_ID_RE.match(text):
        raise UnsafeIdError(f"非法的 id：{value!r}")
    return text


def atomic_write_text(path: str, text: str, encoding: str = "utf-8"):
    """原子地写文本文件（同目录临时文件 + fsync + os.replace）"""
    directory = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".tmp-", suffix=".part")
    try:
        with os.fdopen(fd, "w", encoding=encoding, newline="\n") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def atomic_write_json(path: str, data, **kwargs):
    """原子地写 JSON（默认 ensure_ascii=False，中文可读）"""
    kwargs.setdefault("ensure_ascii", False)
    kwargs.setdefault("indent", 2)
    atomic_write_text(path, json.dumps(data, **kwargs))

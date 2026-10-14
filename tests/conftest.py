"""pytest 夹具调整。

受限沙箱里有两处坑，这里一次性绕开：

1. pytest 的 ``tmp_path_factory`` 会 ``scandir`` 自己的临时根目录，某些环境下
   该目录不可枚举（WinError 5）；
2. Python 新建的目录默认不带沙箱写入所需的权限，必须再 ``chmod`` 一次才能写入。

所以 ``tmp_path`` 改成「工作区内的固定父目录 + ``os.makedirs`` + ``os.chmod``」，
用完由 pytest 清理。
"""

from __future__ import annotations

import os
import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest

_TMP_ROOT = Path(__file__).resolve().parent.parent / ".tmp-pytest"
_counter = 0


@pytest.fixture
def tmp_path() -> Iterator[Path]:
    global _counter
    _counter += 1
    path = _TMP_ROOT / f"case{_counter:04d}"
    os.makedirs(path, exist_ok=True)
    os.chmod(path, 0o777)
    yield path
    shutil.rmtree(path, ignore_errors=True)

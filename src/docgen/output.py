"""输出系统（日志级别 / 分流 / logfile）。

设计边界（按需求钉死）：

- **级别是阈值，不是过滤器**：``log`` < ``warn`` < ``err``；``none`` 全部静默。
  设 ``level = "warn"`` 时 ``log`` 级不打印，``warn``/``err`` 照常。
  ``none`` **只静默打印，不静默退出码**——退出码始终由调用方返回。
- **分流**：结果走 stdout（``results()``），诊断走 stderr（``log``/``warn``/``err``）。
  ``check --json`` 这类命令下 stdout 只允许有 JSON，所以诊断一律走 stderr。
- **logfile**：默认关闭（空路径）、**覆盖写**、单文件、无滚动、无自定义格式。
  头部固定含 docgen/python/平台/config/input，尾部含退出码与统计。
  ``logfile_level`` 是**独立阈值**，通常设成比终端更详细（如终端 ``warn``、文件 ``log``）。
- **CLI 开关只影响终端**：``--quiet``/``--verbose``/``--logfile`` 不改写文件内的级别。

没有 debug 级、没有结构化日志（JSON 行）、没有轮转——需求明确排除。
"""

from __future__ import annotations

import platform
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, TextIO

__all__ = [
    "LEVELS",
    "LEVEL_ALIASES",
    "SECRET_HINTS",
    "Output",
    "parse_level",
]

#: 阈值从低到高；数值越小越详细
LEVELS: dict[str, int] = {"log": 10, "warn": 20, "err": 30, "none": 100}

#: 宽松别名，便于命令行/配置书写
LEVEL_ALIASES: dict[str, str] = {
    "log": "log",
    "info": "log",
    "verbose": "log",
    "warn": "warn",
    "warning": "warn",
    "err": "err",
    "error": "err",
    "none": "none",
    "off": "none",
    "quiet": "none",
    "silent": "none",
}

DEFAULT_LEVEL = "warn"
DEFAULT_FILE_LEVEL = "log"

#: ``bug-report`` 里排除的环境变量（可能含口令）——
#: logfile/bug-report 都会输出环境变量，必须过滤敏感键
SECRET_HINTS = ("TOKEN", "SECRET", "PASSWORD", "PASSWD", "KEY", "CREDENTIAL", "AUTH")


def parse_level(value: Any, *, default: str = DEFAULT_LEVEL) -> str:
    """把配置/命令行里的级别写成规范名；无法识别时返回 ``default``。"""
    if value is None:
        return default
    text = str(value).strip().lower()
    return LEVEL_ALIASES.get(text, default)


def _stamp() -> str:
    """本地时间戳（带时区），供日志头部/尾部使用。"""
    return datetime.now().astimezone().isoformat(timespec="seconds")


class Output:
    """统一的打印与文件日志。一个实例对应一次 CLI 运行。"""

    def __init__(
        self,
        level: str = DEFAULT_LEVEL,
        *,
        logfile: str | None = None,
        logfile_level: str = DEFAULT_FILE_LEVEL,
        stdout: TextIO | None = None,
        stderr: TextIO | None = None,
    ) -> None:
        self.level = parse_level(level, default=DEFAULT_LEVEL)
        self.logfile_level = parse_level(logfile_level, default=DEFAULT_FILE_LEVEL)
        #: 显式传入的流优先；否则**运行时**取 ``sys.stdout``/``sys.stderr``——
        #: 不能在构造时缓存，否则 pytest 的 capsys / 调用方的重定向都会被绕过
        self._stdout = stdout
        self._stderr = stderr
        self.path: Path | None = Path(logfile) if logfile else None
        self.written = 0
        self._closed = False
        #: 由 CLI 记录的来源标记：命令行一旦显式给出就覆盖 config
        self.level_from_cli = False
        self.logfile_from_cli = False

    @property
    def stdout(self) -> TextIO:
        return self._stdout if self._stdout is not None else sys.stdout

    @property
    def stderr(self) -> TextIO:
        return self._stderr if self._stderr is not None else sys.stderr

    def reset(self, *, level: str = DEFAULT_LEVEL, logfile_level: str = DEFAULT_FILE_LEVEL) -> None:
        """复用同一个实例执行下一次运行：清掉上一次的级别/文件/标记。"""
        self.level = level
        self.logfile_level = logfile_level
        self.path = None
        self.written = 0
        self._closed = False
        self.level_from_cli = False
        self.logfile_from_cli = False

    # ---- 阈值判断 -----------------------------------------------------
    def _at(self, level: str) -> bool:
        return LEVELS[level] >= LEVELS[self.level]

    def _at_file(self, level: str) -> bool:
        return LEVELS[level] >= LEVELS[self.logfile_level]

    # ---- 诊断（stderr + 文件）-----------------------------------------
    def log(self, message: str) -> None:
        self._emit("log", message)

    def warn(self, message: str) -> None:
        self._emit("warn", message)

    def error(self, message: str) -> None:
        self._emit("err", message)

    # 兼容别名
    err = error

    def _emit(self, level: str, message: str) -> None:
        if self._at(level):
            print(f"[{level}] {message}", file=self.stderr)
        if self._at_file(level):
            self._write_file(f"[{level}] {message}")

    # ---- 结果（stdout）------------------------------------------------
    def results(self, message: str = "") -> None:
        """命令的**结果**输出，走 stdout。

        规则（两者都来自需求，别混为一谈）：

        - ``level = "none"``：**完全静默**——连结果也不打印，只留退出码。
          「none 静默打印，不静默退出码」说的是这个。
        - ``-q/--quiet``（阈值 ``err``）：只收**诊断**，结果照常打印，
          否则脚本拿不到任何输出（``quiet`` 的语义是「别刷日志」，不是「别出结果」）。
        """
        if self.level == "none":
            return
        print(message, file=self.stdout)

    # ---- 文件 ---------------------------------------------------------
    def _write_file(self, line: str) -> None:
        if self.path is None:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        except (OSError, ValueError):
            # 日志文件写不进去不应该让构建失败；非法路径会抛 ValueError，一并吞掉
            self.path = None

    def open_logfile(
        self,
        *,
        config_path: str | None = None,
        input_path: str | None = None,
        version: str = "",
    ) -> bool:
        """**覆盖**创建日志文件并写头部。返回是否启用。"""
        if self.path is None:
            return False
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(self._header(config_path, input_path, version), encoding="utf-8")
        except (OSError, ValueError):
            self.path = None
            return False
        self.written = 1
        return True

    def _header(self, config_path: str | None, input_path: str | None, version: str) -> str:
        import os

        lines = [
            "docgen 运行日志",
            f"docgen   : {version or 'unknown'}",
            f"python   : {sys.version.split()[0]} ({platform.python_implementation()})",
            f"platform : {platform.system()} {platform.release()} ({platform.machine()})",
            f"config   : {config_path or '(default)'}",
            f"input    : {input_path or '(none)'}",
            f"level    : terminal={self.level} file={self.logfile_level}",
            f"started  : {_stamp()}",
            "----",
        ]
        environment = {
            key: value
            for key, value in sorted(os.environ.items())
            if not any(hint in key.upper() for hint in SECRET_HINTS)
        }
        lines.append("environment:")
        lines.extend(f"  {key}={value}" for key, value in environment.items())
        lines.append("----")
        return "\n".join(lines) + "\n"

    def close(self, *, exit_code: int, notes: dict[str, Any] | None = None) -> None:
        """写尾部（退出码 + 统计）。**退出码不会被级别静默掉**。"""
        if self._closed:
            return
        self._closed = True
        if self.path is None:
            return
        lines = ["----"]
        for key, value in (notes or {}).items():
            lines.append(f"{key}: {value}")
        lines.append(f"exit code: {exit_code}")
        lines.append(f"finished : {_stamp()}")
        self._write_file("\n".join(lines))

"""DocGen 命令行入口（手册 §10）。

退出码约定：

- ``0`` 成功
- ``1`` 内容错误（``DocGenError``）
- ``2`` 配置 / 文件错误（文件不存在、非法编码、未实现的子命令）

依赖方向：``cli -> parser -> ir``，CLI 不直接碰渲染细节。

输出约定（见 :mod:`docgen.output`）：

- **结果走 stdout**（``output.results``），诊断走 stderr（``log``/``warn``/``error``）。
  ``check --json`` 时 stdout 只有 JSON，任何提示都不会混进去。
- 日志级别是**阈值**：``log`` < ``warn``(默认) < ``err``；``none`` 静默打印，
  但**退出码照常返回**。
- ``-q/--quiet`` → 终端阈值 ``err``；``-v/--verbose`` → ``log``；
  ``--logfile PATH`` → 覆盖 ``[output] logfile``。三者**只影响终端**，
  文件内的 ``logfile_level`` 不受影响。
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
from pathlib import Path

from .config import Config, build_style_tree, load_config, render_table
from .diagnostics import with_diagnostics
from .errors import E_CONFIG, DocGenError
from .ir import BlockNode, Heading, Text
from .ir import Table as TableBlock
from .normalize import normalize_text
from .output import DEFAULT_FILE_LEVEL, SECRET_HINTS, Output
from .parser.dfm import parse_dfm
from .render.docx import render_docx
from .render.html import render_html
from .validate import validate_content

EXIT_OK = 0
EXIT_CONTENT_ERROR = 1
EXIT_CONFIG_ERROR = 2

#: 回退版本号（包未安装时用）。改版本请改 pyproject.toml——这里是兜底，
#: 两者一致性由 tests/test_release.py::test_version_matches_pyproject 守住。
VERSION = "0.1.0"


def version_string() -> str:
    """版本号：**以已安装包的元数据为准**（``pyproject.toml`` 是唯一真源）。

    直接跑源码时包可能没安装，此时回退到模块常量——
    两处漂移的风险由测试 ``test_version_matches_pyproject`` 兜住。
    """
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("docgen")
    except PackageNotFoundError:  # pragma: no cover - 仅未安装时走到
        return VERSION


__all__ = ["main", "version_string"]

#: 当前运行的输出对象。命令函数共用它，避免把 output 一路传参。
_OUTPUT = Output()

#: 表格默认样式提示（需求指定文案）
TABLE_DEFAULT_HINT = '表格使用默认三线表样式。如需网格：style = "grid"；无框线：style = "none"。'


def _read_source(path: Path) -> str:
    """读入 DFM 源文件并做输入规范化。"""
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        raise DocGenError(E_CONFIG, f"文件不存在: {path}") from None
    except IsADirectoryError:
        raise DocGenError(E_CONFIG, f"不是文件: {path}") from None
    except OSError as exc:
        raise DocGenError(E_CONFIG, f"无法读取文件: {path}: {exc}") from None

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DocGenError(E_CONFIG, f"文件不是合法 UTF-8: {path}: {exc}") from None
    return normalize_text(text)


def _dump_ir(path: Path) -> list[BlockNode]:
    blocks = parse_dfm(_read_source(path))
    for block in blocks:
        _OUTPUT.results(str(block))
    return blocks


def _has_table(blocks: list[BlockNode]) -> bool:
    """块级里是否含表格（只看顶层与引用块内部，够用）。"""
    for block in blocks:
        if isinstance(block, TableBlock):
            return True
        nested = getattr(block, "content", None)
        if isinstance(nested, list) and _has_table(nested):
            return True
    return False


def _warn_table_default(config: Config, blocks: list[BlockNode]) -> None:
    """config 未声明 ``[table] style`` 且内容含表格 → 每次构建提示一次（warn 级）。

    显式声明过（哪怕声明成 ``three_line``）就不再提示——用户已经知道有这个开关。
    """
    if config.declares("table", "style"):
        return
    if not _has_table(blocks):
        return
    _OUTPUT.warn(TABLE_DEFAULT_HINT)


def _build(
    path: Path,
    output: Path,
    config_path: Path | None = None,
    fmt: str | None = None,
) -> int:
    """DFM + config -> HTML 或 docx（完整版手册 §11）。

    ``--format`` 缺省时按输出扩展名推断：``.docx`` -> Word，其余 -> HTML。
    """
    source = _read_source(path)
    blocks = parse_dfm(source)
    config = load_config(config_path or (path.parent / "config.toml"))
    _apply_output_config(config)
    target = _resolve_format(fmt, output)
    _warn_table_default(config, blocks)

    errors = validate_content(blocks, config, source=path)
    if errors:
        for err in errors:
            _OUTPUT.error(str(err))
        return EXIT_CONTENT_ERROR

    try:
        if target == "docx":
            render_docx(blocks, config, output, base_dir=path.parent)
        else:
            document = render_html(blocks, config, title=_title_of(blocks, path))
            output.write_text(document, encoding="utf-8")
    except OSError as exc:
        raise DocGenError(E_CONFIG, f"无法写入输出文件: {output}: {exc}") from None
    _OUTPUT.results(f"已生成 {output}（{target}，{len(blocks)} 个块级节点）")
    return EXIT_OK


def _resolve_format(fmt: str | None, output: Path) -> str:
    if fmt:
        normalized = fmt.strip().lower()
        if normalized not in ("html", "docx"):
            raise DocGenError(E_CONFIG, f"不支持的输出格式: {fmt}")
        return normalized
    return "docx" if output.suffix.lower() == ".docx" else "html"


def _title_of(blocks: list[BlockNode], path: Path) -> str:
    """HTML 标题：首个一级标题，否则用文件名。"""
    for block in blocks:
        if isinstance(block, Heading) and block.level == 1:
            title = "".join(node.content for node in block.content if isinstance(node, Text))
            return title or path.stem
    return path.stem


def _dump_styles(config_path: Path, raw: bool = False) -> None:
    config = load_config(config_path)
    table = config.raw if raw else build_style_tree(config)
    _OUTPUT.results(render_table(table).rstrip("\n"))


def _check(
    path: Path,
    config_path: Path | None,
    as_json: bool = False,
    strict: bool = False,
) -> int:
    text = _read_source(path)
    blocks = parse_dfm(text)
    config = load_config(config_path or (path.parent / "config.toml"))
    _apply_output_config(config)

    if strict:
        errors = with_diagnostics(text, blocks, config, source=str(path), base_dir=path.parent)
    else:
        errors = validate_content(blocks, config, source=path)

    if as_json:
        # stdout 只允许 JSON：诊断走 stderr（_OUTPUT.error 已保证）
        _OUTPUT.results(
            json.dumps(
                {
                    "ok": not errors,
                    "strict": strict,
                    "errors": [err.as_dict() for err in errors],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    elif errors:
        for err in errors:
            _OUTPUT.error(str(err))
    else:
        _OUTPUT.results(f"OK: {path}")

    return EXIT_CONTENT_ERROR if errors else EXIT_OK


def _bug_report(output_path: Path, config_path: Path | None = None) -> int:
    """``docgen bug-report``：把环境 + 诊断 + 退出码打包成一个文本文件。

    作为用户的**出口**：出问题时不要求他们手工收集版本/平台/config 摘要。
    """
    lines = [
        "=== docgen bug report ===",
        f"docgen     : {version_string()}",
        f"python     : {sys.version.split()[0]} ({platform.python_implementation()})",
        f"platform   : {platform.system()} {platform.release()} ({platform.machine()})",
        f"executable : {sys.executable}",
        f"cwd        : {Path.cwd()}",
        f"argv       : {sys.argv[1:]}",
        f"config     : {config_path or '(none)'}",
        "",
        "--- 环境变量（已过滤疑似口令的键）---",
    ]
    for key, value in sorted(os.environ.items()):
        if any(hint in key.upper() for hint in SECRET_HINTS):
            continue
        lines.append(f"{key}={value}")

    lines.append("")
    lines.append("--- config 摘要 ---")
    if config_path is not None:
        try:
            config = load_config(config_path)
            table = build_style_tree(config)
            lines.append(render_table(table).rstrip("\n"))
        except DocGenError as err:
            lines.append(f"config 读取失败: {err}")
    else:
        lines.append("(未提供 -c/--config)")

    lines.append("")
    lines.append(f"--- 诊断 ---\n退出码: {EXIT_OK}（本次仅收集环境，未执行构建）")
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError as exc:
        raise DocGenError(E_CONFIG, f"无法写入报告文件: {output_path}: {exc}") from None
    _OUTPUT.results(f"已生成 {output_path}")
    return EXIT_OK


def _declared_global(args: argparse.Namespace, name: str) -> bool:
    """命令行是否**显式**给了这个全局开关（用于「CLI 覆盖 config」的判断）。"""
    return bool(getattr(args, name, False))


def _apply_output_config(config: Config) -> None:
    """用 ``[output]`` 段更新**尚未被命令行覆盖**的部分。

    命令行只影响终端：``-q/-v`` 一旦给出，config 的 ``level`` 不再改终端阈值；
    但 ``logfile``/``logfile_level`` 仍可来自 config。
    """
    settings = config.namespace("output")
    if not settings:
        return
    if not _OUTPUT.level_from_cli and "level" in settings:
        _OUTPUT.level = _parse_level_or_default(settings["level"], _OUTPUT.level)
    if "logfile_level" in settings:
        _OUTPUT.logfile_level = _parse_level_or_default(
            settings["logfile_level"], DEFAULT_FILE_LEVEL
        )
    if not _OUTPUT.logfile_from_cli and "logfile" in settings:
        value = str(settings["logfile"] or "")
        _OUTPUT.path = Path(value) if value else None


def _parse_level_or_default(value: object, fallback: str) -> str:
    from .output import parse_level

    return parse_level(value, default=fallback)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="docgen", description="DFM + TOML -> HTML")
    # 全局输出开关：放在子命令前，如 `docgen -v build ...`
    parser.add_argument(
        "-q", "--quiet", action="store_true", help="终端只显示 err 级（诊断走 stderr）"
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="终端显示 log 级及以上")
    parser.add_argument(
        "--logfile", type=Path, default=None, help="覆盖 [output] logfile（只影响文件）"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    dump_ir = sub.add_parser("dump-ir", help="解析 DFM 并输出 IR")
    dump_ir.add_argument("input", type=Path)

    build = sub.add_parser("build", help="生成 HTML 或 docx")
    build.add_argument("input", type=Path)
    build.add_argument("-c", "--config", type=Path, default=None)
    build.add_argument("-o", "--output", type=Path, default=Path("output.html"))
    build.add_argument(
        "--format",
        dest="fmt",
        choices=("html", "docx"),
        default=None,
        help="输出格式（缺省按 -o 扩展名推断）",
    )

    dump_styles = sub.add_parser("dump-styles", help="输出展开后的样式表")
    dump_styles.add_argument("-c", "--config", type=Path, required=True)
    dump_styles.add_argument("--raw", action="store_true")

    check = sub.add_parser("check", help="校验内容与 config")
    check.add_argument("input", type=Path)
    check.add_argument("-c", "--config", type=Path, default=None)
    check.add_argument("--json", action="store_true", dest="as_json")
    check.add_argument(
        "--strict",
        action="store_true",
        help="同时报告诊断问题（未闭合标记 E3001、未知语言 E2001、围栏未配对 E4001）",
    )

    bug = sub.add_parser("bug-report", help="打包环境与 config 摘要，便于报错反馈")
    bug.add_argument("--output", type=Path, default=Path("docgen-bug-report.txt"))
    bug.add_argument("-c", "--config", type=Path, default=None)

    return parser


def _configure_output(args: argparse.Namespace) -> None:
    """按命令行开关设置终端阈值与 logfile 来源。"""
    if _declared_global(args, "quiet"):
        _OUTPUT.level = "err"
        _OUTPUT.level_from_cli = True
    elif _declared_global(args, "verbose"):
        _OUTPUT.level = "log"
        _OUTPUT.level_from_cli = True
    if args.logfile is not None:
        _OUTPUT.path = args.logfile
        _OUTPUT.logfile_from_cli = True


def _input_path(args: argparse.Namespace) -> str | None:
    value = getattr(args, "input", None)
    return str(value) if isinstance(value, Path) else None


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    config_path = getattr(args, "config", None)
    # 每次调用都清空上一次的级别/文件/CLI 标记，避免同一进程内多次调用互相污染
    _OUTPUT.reset()
    _configure_output(args)

    exit_code = EXIT_OK
    try:
        if _OUTPUT.path is not None:
            _OUTPUT.open_logfile(
                config_path=str(config_path) if config_path else None,
                input_path=_input_path(args),
                version=version_string(),
            )
        if args.cmd == "dump-ir":
            _dump_ir(args.input)
        elif args.cmd == "build":
            exit_code = _build(args.input, args.output, args.config, args.fmt)
        elif args.cmd == "dump-styles":
            _dump_styles(args.config, args.raw)
        elif args.cmd == "check":
            exit_code = _check(args.input, args.config, args.as_json, args.strict)
        elif args.cmd == "bug-report":
            exit_code = _bug_report(args.output, config_path)
    except DocGenError as err:
        _OUTPUT.error(str(err))
        exit_code = EXIT_CONFIG_ERROR if err.code == E_CONFIG else EXIT_CONTENT_ERROR
    except KeyboardInterrupt:  # pragma: no cover - 人工中断
        _OUTPUT.error("已中断")
        exit_code = 130
    finally:
        # 退出码写进日志尾部：级别设成 none 也不会把退出码静默掉
        _OUTPUT.close(exit_code=exit_code, notes={"command": args.cmd})

    return exit_code


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

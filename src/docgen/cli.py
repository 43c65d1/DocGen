"""DocGen 命令行入口（手册 §10）。

退出码约定：

- ``0`` 成功
- ``1`` 内容错误（``DocGenError``）
- ``2`` 配置 / 文件错误（文件不存在、非法编码、未实现的子命令）

依赖方向：``cli -> parser -> ir``，CLI 不直接碰渲染细节。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import build_style_tree, load_config, render_table
from .diagnostics import with_diagnostics
from .errors import E_CONFIG, DocGenError
from .ir import BlockNode, Heading, Text
from .normalize import normalize_text
from .parser.dfm import parse_dfm
from .render.html import render_html
from .validate import validate_content

EXIT_OK = 0
EXIT_CONTENT_ERROR = 1
EXIT_CONFIG_ERROR = 2

__all__ = ["main"]


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
        print(block)
    return blocks


def _build(path: Path, output: Path, config_path: Path | None = None) -> int:
    """DFM + config -> HTML 文件（第 4 周端到端链路）。"""
    blocks = parse_dfm(_read_source(path))
    config = load_config(config_path or (path.parent / "config.toml"))

    errors = validate_content(blocks, config, source=path)
    if errors:
        for err in errors:
            print(err, file=sys.stderr)
        return EXIT_CONTENT_ERROR

    document = render_html(blocks, config, title=_title_of(blocks, path))
    try:
        output.write_text(document, encoding="utf-8")
    except OSError as exc:
        raise DocGenError(E_CONFIG, f"无法写入输出文件: {output}: {exc}") from None
    print(f"已生成 {output}（{len(blocks)} 个块级节点）")
    return EXIT_OK


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
    sys.stdout.write(render_table(table))


def _check(
    path: Path,
    config_path: Path | None,
    as_json: bool = False,
    strict: bool = False,
) -> int:
    text = _read_source(path)
    blocks = parse_dfm(text)
    config = load_config(config_path or (path.parent / "config.toml"))

    if strict:
        errors = with_diagnostics(text, blocks, config, source=str(path), base_dir=path.parent)
    else:
        errors = validate_content(blocks, config, source=path)

    if as_json:
        print(
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
            print(err, file=sys.stderr)
    else:
        print(f"OK: {path}")

    return EXIT_CONTENT_ERROR if errors else EXIT_OK


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="docgen", description="DFM + TOML -> HTML")
    sub = parser.add_subparsers(dest="cmd", required=True)

    dump_ir = sub.add_parser("dump-ir", help="解析 DFM 并输出 IR")
    dump_ir.add_argument("input", type=Path)

    build = sub.add_parser("build", help="生成 HTML")
    build.add_argument("input", type=Path)
    build.add_argument("-c", "--config", type=Path, default=None)
    build.add_argument("-o", "--output", type=Path, default=Path("output.html"))

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

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    try:
        if args.cmd == "dump-ir":
            _dump_ir(args.input)
        elif args.cmd == "build":
            return _build(args.input, args.output, args.config)
        elif args.cmd == "dump-styles":
            _dump_styles(args.config, args.raw)
        elif args.cmd == "check":
            return _check(args.input, args.config, args.as_json, args.strict)
    except DocGenError as err:
        print(err, file=sys.stderr)
        return EXIT_CONFIG_ERROR if err.code == E_CONFIG else EXIT_CONTENT_ERROR
    except KeyboardInterrupt:  # pragma: no cover - 人工中断
        print("已中断", file=sys.stderr)
        return 130

    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

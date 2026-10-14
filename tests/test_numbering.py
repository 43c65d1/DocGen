"""编号 / 题注 / 交叉引用契约（完整版手册 §6.2.6 / W3）。

- 标题多级编号：``HeadingN`` → ``ilvl = N-1``（母版里的 ``numId=100``）
- 图/表/公式题注：``\\begin{caption #fig:1}`` → ``Caption`` 节点 + `SEQ` 域
- 交叉引用：``[[ref:fig:1]]`` → `Ref` 行内节点 → `REF` 域；目标不存在报 ``E5004``
- 目录占位：``[[toc]]`` → ``Toc`` 块
"""

from __future__ import annotations

from pathlib import Path

from docgen import errors
from docgen.config import Config, load_config
from docgen.diagnostics import scan_source
from docgen.ir import (
    Heading,
    ListBlock,
    NamedBlock,
    PageBreak,
    Paragraph,
    Ref,
    Text,
    Toc,
)
from docgen.parser.dfm import parse_dfm

CONFIG = """\
config_version = "0.1"

[styles.caption]
font.name = "宋体"
font.size = "10.5pt"

[styles.body]
font.size = "12pt"
"""


def _config(tmp_path: Path) -> Config:
    path = tmp_path / "config.toml"
    path.write_text(CONFIG, encoding="utf-8")
    return load_config(path)


# --------------------------------------------------------------------------
# 新标记
# --------------------------------------------------------------------------
def test_ref_marker_becomes_inline_ref() -> None:
    assert parse_dfm("见图 [[ref:fig:1]]。\n") == [
        Paragraph(
            content=[Text("见图 "), Ref(target="fig:1"), Text("。")],
            source_line=1,
        )
    ]


def test_toc_marker_becomes_block() -> None:
    assert parse_dfm("[[toc]]\n") == [Toc(source_line=1)]


def test_label_collected_from_caption_block() -> None:
    blocks = parse_dfm("\\begin{caption #fig:1}\n图 1 架构\n\\end{caption}\n")
    caption = blocks[0]
    assert isinstance(caption, NamedBlock)
    assert caption.label == "fig:1"
    assert caption.name == "caption"


def test_label_collected_from_named_equation() -> None:
    blocks = parse_dfm("\\begin{equation #eq:main}\n$$E=mc^2$$\n\\end{equation}\n")
    block = blocks[0]
    assert isinstance(block, NamedBlock)
    assert block.label == "eq:main"


def test_unclosed_ref_marker_is_diagnostic() -> None:
    found = scan_source("见图 [[ref:fig:1\n", ("unclosed",))
    assert [err.code for err in found] == [errors.E_UNCLOSED_MARKER]


def test_toc_marker_is_not_a_diagnostic() -> None:
    assert scan_source("[[toc]]\n", ("unclosed",)) == []


# --------------------------------------------------------------------------
# 编号映射
# --------------------------------------------------------------------------
def test_heading_numbering_map_is_explicit() -> None:
    from docgen.numbering import heading_numbering

    mapping = heading_numbering()
    assert mapping[1] == (0, "Heading1")
    assert mapping[3] == (2, "Heading3")
    assert set(mapping) == set(range(1, 10))


def test_caption_kinds_are_defined() -> None:
    from docgen.numbering import CAPTION_KINDS

    assert CAPTION_KINDS["figure"] == "图"
    assert CAPTION_KINDS["table"] == "表"
    assert CAPTION_KINDS["equation"] == "公式"


def test_collect_labels_returns_all_targets() -> None:
    from docgen.numbering import collect_labels

    blocks = parse_dfm(
        "\\begin{caption #fig:1}\n图一\n\\end{caption}\n\n"
        "\\begin{table #tab:1}\n表一\n\\end{table}\n\n"
        "\\begin{equation #eq:1}\n$$x$$\n\\end{equation}\n"
    )
    labels = collect_labels(blocks)
    assert labels == {"fig:1": "figure", "tab:1": "table", "eq:1": "equation"}


def test_collect_refs_finds_targets() -> None:
    from docgen.numbering import collect_refs

    blocks = parse_dfm("见图 [[ref:fig:1]] 与 [[ref:tab:1]]。\n")
    refs = collect_refs(blocks)
    assert [ref.target for ref in refs] == ["fig:1", "tab:1"]
    assert refs[0].source_line == 1


def test_collect_refs_walks_nested_blocks() -> None:
    from docgen.numbering import collect_refs

    blocks = parse_dfm("> 引用里的 [[ref:eq:1]]\n\n- 列表里的 [[ref:fig:2]]\n")
    assert {ref.target for ref in collect_refs(blocks)} == {"eq:1", "fig:2"}


def test_caption_counters_number_per_kind() -> None:
    from docgen.numbering import caption_counters

    blocks = parse_dfm(
        "\\begin{caption #fig:1}\n一\n\\end{caption}\n\n"
        "\\begin{caption #fig:2}\n二\n\\end{caption}\n\n"
        "\\begin{table #tab:1}\n表\n\\end{table}\n"
    )
    counters = caption_counters(blocks)
    assert counters == {"fig:1": 1, "fig:2": 2, "tab:1": 1}


# --------------------------------------------------------------------------
# 校验：E5004
# --------------------------------------------------------------------------
def test_unknown_reference_is_content_error(tmp_path: Path) -> None:
    from docgen.numbering import validate_numbering

    config = _config(tmp_path)
    blocks = parse_dfm("见图 [[ref:fig:99]]。\n")
    found = validate_numbering(blocks, config, source="doc.md")
    assert [err.code for err in found] == [errors.E_UNKNOWN_REF]
    assert found[0].line == 1
    assert "fig:99" in found[0].message


def test_known_reference_passes(tmp_path: Path) -> None:
    from docgen.numbering import validate_numbering

    config = _config(tmp_path)
    blocks = parse_dfm("\\begin{caption #fig:1}\n图一\n\\end{caption}\n\n见图 [[ref:fig:1]]。\n")
    assert validate_numbering(blocks, config, source="doc.md") == []


def test_duplicate_label_is_content_error(tmp_path: Path) -> None:
    from docgen.numbering import validate_numbering

    config = _config(tmp_path)
    blocks = parse_dfm(
        "\\begin{caption #fig:1}\n一\n\\end{caption}\n\n"
        "\\begin{caption #fig:1}\n重复\n\\end{caption}\n"
    )
    found = validate_numbering(blocks, config, source="doc.md")
    assert [err.code for err in found] == [errors.E_SYNTAX]
    assert "重复" in found[0].message


def test_check_strict_reports_unknown_reference(tmp_path: Path) -> None:
    from docgen.diagnostics import with_diagnostics

    config = _config(tmp_path)
    text = "见图 [[ref:fig:99]]。\n"
    found = with_diagnostics(text, parse_dfm(text), config)
    assert [err.code for err in found] == [errors.E_UNKNOWN_REF]


# --------------------------------------------------------------------------
# 题注与引用在 IR 层的位置
# --------------------------------------------------------------------------
def test_caption_content_is_parsed(tmp_path: Path) -> None:
    blocks = parse_dfm("\\begin{caption #fig:1}\n图 1 系统架构\n\\end{caption}\n")
    block = blocks[0]
    assert isinstance(block, NamedBlock)
    assert block.content[0] == Paragraph(content=[Text("图 1 系统架构")], source_line=1)


def test_numbering_does_not_break_existing_nodes() -> None:
    """回归：新标记不影响既有块级解析。"""
    blocks = parse_dfm("# 标题\n\n- 项\n\n[[pagebreak]]\n")
    assert isinstance(blocks[0], Heading)
    assert isinstance(blocks[1], ListBlock)
    assert isinstance(blocks[2], PageBreak)

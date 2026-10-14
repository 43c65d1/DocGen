"""公式编号契约（完整版手册 W3 / §6.2.5）。

带编号的公式用 ``\\begin{equation #eq:1 number=1}`` 包裹：渲染成**无边框三列表格**
（左空 / 中公式 / 右编号），编号用书签以便 ``[[ref:eq:1]]`` 引用。
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

from docgen.config import Config, load_config
from docgen.ir import Formula, NamedBlock
from docgen.parser.dfm import parse_dfm
from docgen.render.docx import render_docx_bytes

FIXTURES = Path(__file__).parent / "fixtures"


def _config(tmp_path: Path) -> Config:
    path = tmp_path / "config.toml"
    path.write_text('config_version = "0.1"\n\n[math]\nengine = "plain"\n', encoding="utf-8")
    return load_config(path)


def _document_xml(tmp_path: Path, markdown: str) -> str:
    data = render_docx_bytes(parse_dfm(markdown), _config(tmp_path))
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return archive.read("word/document.xml").decode("utf-8")


# --------------------------------------------------------------------------
# 解析：编号属性
# --------------------------------------------------------------------------
def test_equation_block_keeps_label_and_number() -> None:
    blocks = parse_dfm("\\begin{equation #eq:1 number=1}\n$$x=1$$\n\\end{equation}\n")
    block = blocks[0]
    assert isinstance(block, NamedBlock)
    assert block.label == "eq:1"
    assert block.attributes["number"] == "1"
    assert isinstance(block.content[0], Formula)


def test_equation_block_without_number_is_unnumbered() -> None:
    blocks = parse_dfm("\\begin{equation #eq:2}\n$$x=2$$\n\\end{equation}\n")
    block = blocks[0]
    assert isinstance(block, NamedBlock)
    assert "number" not in block.attributes


def test_equation_body_is_display_math() -> None:
    blocks = parse_dfm("\\begin{equation #eq:3}\n$$\nE = mc^2\n$$\n\\end{equation}\n")
    block = blocks[0]
    assert isinstance(block, NamedBlock)
    formula = block.content[0]
    assert isinstance(formula, Formula)
    assert formula.display is True
    assert "mc^2" in formula.latex


def test_numbering_helpers_expose_equation_labels() -> None:
    from docgen.numbering import caption_counters, collect_labels

    blocks = parse_dfm(
        "\\begin{equation #eq:1 number=1}\n$$x$$\n\\end{equation}\n\n"
        "\\begin{equation #eq:2 number=2}\n$$y$$\n\\end{equation}\n"
    )
    assert collect_labels(blocks) == {"eq:1": "equation", "eq:2": "equation"}
    assert caption_counters(blocks) == {"eq:1": 1, "eq:2": 2}


# --------------------------------------------------------------------------
# 渲染：无边框三列表格
# --------------------------------------------------------------------------
def test_numbered_formula_uses_three_column_table(tmp_path: Path) -> None:
    document = _document_xml(
        tmp_path, "\\begin{equation #eq:1 number=1}\n$$x=1$$\n\\end{equation}\n"
    )
    assert "<w:tbl>" in document
    assert "x=1" in document
    assert "1" in document
    # 无边框：表格边框全部 none
    assert 'w:val="none"' in document
    assert "bookmarkStart" in document
    assert 'w:name="eq:1"' in document


def test_unnumbered_formula_is_plain_paragraph(tmp_path: Path) -> None:
    document = _document_xml(tmp_path, "\\begin{equation #eq:2}\n$$x=2$$\n\\end{equation}\n")
    assert "<w:tbl>" not in document
    assert "x=2" in document


def test_formula_number_can_be_referenced(tmp_path: Path) -> None:
    document = _document_xml(
        tmp_path,
        "\\begin{equation #eq:1 number=1}\n$$x=1$$\n\\end{equation}\n\n见式 [[ref:eq:1]]。\n",
    )
    assert "REF eq:1" in document


def test_plain_formula_paragraph_is_not_indented(tmp_path: Path) -> None:
    """块级公式（独立段落）不应带首行缩进，否则居中会偏。"""
    document = _document_xml(tmp_path, "$$\nx=1\n$$\n")
    assert "firstLineChars" not in document or 'w:val="0"' in document

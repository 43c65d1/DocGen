"""行距：倍数（1.5）与固定磅值（"20pt"）两种语义。"""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

import pytest

from docgen.config import Config, load_config
from docgen.errors import DocGenError
from docgen.ir import Paragraph, Text
from docgen.parser.dfm import parse_dfm
from docgen.render.docx import render_docx_bytes
from docgen.render.ooxml import parse_line_spacing

BASE = 'config_version = "0.1"\n\n[document]\nfont.name = "宋体"\n'


def _config(tmp_path: Path, extra: str = "") -> Config:
    path = tmp_path / "c.toml"
    path.write_text(BASE + extra, encoding="utf-8")
    return load_config(path)


def _document_xml(tmp_path: Path, markdown: str = "正文。\n", extra: str = "") -> str:
    data = render_docx_bytes(parse_dfm(markdown), _config(tmp_path, extra), base_dir=tmp_path)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return archive.read("word/document.xml").decode("utf-8")


def _spacings(xml: str) -> list[str]:
    return re.findall(r"<w:spacing [^/]*/>", xml)


# --------------------------------------------------------------------------
# 解析
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (1.5, 1.5),
        ("1.5", 1.5),
        ("1.5倍", 1.5),
        ("1.5 lines", 1.5),
        (2, 2.0),
    ],
)
def test_parse_multiple(value: object, expected: float) -> None:
    assert parse_line_spacing(value) == expected


@pytest.mark.parametrize(("value", "points"), [("20pt", 20.0), ("20磅", 20.0), ("18pt", 18.0)])
def test_parse_exact_points(value: str, points: float) -> None:
    length = parse_line_spacing(value)
    assert getattr(length, "pt", None) == pytest.approx(points)


@pytest.mark.parametrize("value", ["abc", "20 px", -1, 0, True, "0pt"])
def test_parse_invalid_raises_e5001(value: object) -> None:
    with pytest.raises(DocGenError) as caught:
        parse_line_spacing(value)
    assert caught.value.code == "E5001"


# --------------------------------------------------------------------------
# 渲染
# --------------------------------------------------------------------------
def test_document_fixed_line_spacing(tmp_path: Path) -> None:
    xml = _document_xml(tmp_path, extra='\nline_spacing = "20pt"\n')
    spacing = _spacings(xml)[0]
    assert 'w:line="400"' in spacing
    assert 'w:lineRule="exact"' in spacing


def test_document_multiple_line_spacing(tmp_path: Path) -> None:
    xml = _document_xml(tmp_path, extra="\nline_spacing = 1.5\n")
    spacing = _spacings(xml)[0]
    assert 'w:line="360"' in spacing
    assert 'w:lineRule="auto"' in spacing


def test_body_style_fixed_line_spacing(tmp_path: Path) -> None:
    xml = _document_xml(tmp_path, extra='\n[styles.body]\nline_spacing = "22pt"\n')
    spacing = _spacings(xml)[0]
    assert 'w:line="440"' in spacing
    assert 'w:lineRule="exact"' in spacing


def test_table_text_fixed_line_spacing(tmp_path: Path) -> None:
    xml = _document_xml(
        tmp_path,
        markdown="| a |\n| --- |\n| 1 |\n",
        extra='\n[table.text]\nline_spacing = "18pt"\n',
    )
    cell = re.search(r"<w:tc>.*?</w:tc>", xml, re.DOTALL)
    assert cell is not None
    assert 'w:line="360"' in cell.group(0)
    assert 'w:lineRule="exact"' in cell.group(0)


def test_invalid_document_line_spacing_is_content_error(tmp_path: Path) -> None:
    with pytest.raises(DocGenError) as caught:
        _document_xml(tmp_path, extra='\nline_spacing = "20 px"\n')
    assert caught.value.code == "E5001"


def test_paragraph_named_block_inherits_document_fixed_spacing(tmp_path: Path) -> None:
    """段落级没有覆盖时，样式里的固定行距要继承下去（不是退回倍数）。"""
    xml = _document_xml(
        tmp_path,
        markdown="正文。\n\n> 引用。\n",
        extra='\nline_spacing = "20pt"\n',
    )
    for spacing in _spacings(xml):
        assert 'w:lineRule="exact"' in spacing
        assert 'w:line="400"' in spacing


def test_line_spacing_does_not_break_inline_bold(tmp_path: Path) -> None:
    """既有行内样式（粗体）不应因为行距解析而丢内容。"""
    data = render_docx_bytes(
        [Paragraph(source_line=1, content=[Text(content="**粗体**")])],
        _config(tmp_path, extra='\nline_spacing = "20pt"\n'),
    )
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        xml = archive.read("word/document.xml").decode("utf-8")
    assert "**粗体**" in xml  # 纯文本 IR 不会被解析成 markdown

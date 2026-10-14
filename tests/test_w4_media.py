"""图片与脚注契约（完整版手册 W4）。

- **图片**：``[[img:path]]`` 支持尺寸（``.cm``/``.in``/``px``）与对齐，允许 config 给默认值
- **脚注**：``[[fn:文字]]`` 行内脚注 → 引用 run + 手写 ``word/footnotes.xml``
"""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

from docgen.config import Config, load_config
from docgen.ir import Footnote, ImageBlock, Paragraph, Text
from docgen.parser.dfm import parse_dfm
from docgen.render.docx import render_docx_bytes

FIXTURES = Path(__file__).parent / "fixtures"

BASE = """\
config_version = "0.1"

[image]
width = "4cm"
align = "center"

[math]
engine = "plain"
"""


def _config(tmp_path: Path, extra: str = BASE) -> Config:
    path = tmp_path / "config.toml"
    path.write_text(extra, encoding="utf-8")
    return load_config(path)


def _document_xml(tmp_path: Path, markdown: str, extra: str = BASE) -> str:
    data = render_docx_bytes(parse_dfm(markdown), _config(tmp_path, extra), base_dir=FIXTURES)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return archive.read("word/document.xml").decode("utf-8")


# --------------------------------------------------------------------------
# 图片尺寸与对齐
# --------------------------------------------------------------------------
def test_image_attribute_width_is_applied(tmp_path: Path) -> None:
    """``[[img:pics/photo.png width=2cm]]`` → ``wp:extent`` 为 2cm。"""
    document = _document_xml(tmp_path, "[[img:pics/photo.png width=2cm]]\n")
    extents = re.findall(r'<wp:extent cx="(\d+)" cy="(\d+)"/>', document)
    assert extents
    cx = int(extents[0][0])
    # 2cm = 720000 EMU（1cm = 360000 EMU）
    assert abs(cx - 720000) <= 2000


def test_image_config_width_applies(tmp_path: Path) -> None:
    document = _document_xml(tmp_path, "[[img:pics/photo.png]]\n")
    extents = re.findall(r'<wp:extent cx="(\d+)"', document)
    assert extents
    assert abs(int(extents[0]) - 1440000) <= 2000  # 4cm


def test_image_alignment_from_config(tmp_path: Path) -> None:
    document = _document_xml(tmp_path, "[[img:pics/photo.png]]\n")
    assert 'w:val="center"' in document


def test_image_attribute_overrides_config(tmp_path: Path) -> None:
    document = _document_xml(tmp_path, "[[img:pics/photo.png width=1cm align=left]]\n")
    assert abs(int(re.findall(r'<wp:extent cx="(\d+)"', document)[0]) - 360000) <= 2000
    assert 'w:val="left"' in document


def test_image_without_config_keeps_natural_size(tmp_path: Path) -> None:
    """不给尺寸时保持图片原始尺寸（不等于 config 的 4cm）。"""
    document = _document_xml(tmp_path, "[[img:pics/photo.png]]\n", 'config_version = "0.1"\n')
    assert "wp:extent" in document


def test_missing_image_still_reported(tmp_path: Path) -> None:
    document = _document_xml(tmp_path, "[[img:pics/none.png width=2cm]]\n")
    assert "图片缺失" in document


# --------------------------------------------------------------------------
# 脚注
# --------------------------------------------------------------------------
def test_footnote_marker_parses() -> None:
    blocks = parse_dfm("正文[[fn:这是脚注]]。\n")
    assert blocks == [
        Paragraph(
            content=[Text("正文"), Footnote(text="这是脚注"), Text("。")],
            source_line=1,
        )
    ]


def test_footnote_in_paragraph_only() -> None:
    """``[[fn:]]`` 独占一段时也是段落里的脚注引用。"""
    blocks = parse_dfm("[[fn:独立脚注]]\n")
    assert isinstance(blocks[0], Paragraph)
    assert isinstance(blocks[0].content[0], Footnote)


def test_footnotes_part_is_created(tmp_path: Path) -> None:
    """手写 ``word/footnotes.xml``：必须写入引用与脚注文本，并挂在包关系里。"""
    data = render_docx_bytes(parse_dfm("正文[[fn:脚注内容]]\n"), _config(tmp_path))
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = archive.namelist()
        footnotes = archive.read("word/footnotes.xml").decode("utf-8")
        rels = archive.read("word/_rels/document.xml.rels").decode("utf-8")
        content_types = archive.read("[Content_Types].xml").decode("utf-8")
    assert "word/footnotes.xml" in names
    assert "脚注内容" in footnotes
    assert "footnotes.xml" in rels
    assert "footnotes+xml" in content_types


def test_footnote_reference_in_document(tmp_path: Path) -> None:
    document = _document_xml(tmp_path, "正文[[fn:脚注内容]]\n")
    assert "footnoteReference" in document
    assert 'w:id="1"' in document


def test_multiple_footnotes_get_distinct_ids(tmp_path: Path) -> None:
    data = render_docx_bytes(parse_dfm("一[[fn:甲]] 二[[fn:乙]]\n"), _config(tmp_path))
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        footnotes = archive.read("word/footnotes.xml").decode("utf-8")
    assert 'w:id="1"' in footnotes and 'w:id="2"' in footnotes
    assert "甲" in footnotes and "乙" in footnotes


def test_no_footnotes_no_part(tmp_path: Path) -> None:
    """没有脚注时不该生成 footnotes 部件（避免多余部件）。"""
    data = render_docx_bytes(parse_dfm("普通段落\n"), _config(tmp_path))
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        assert "word/footnotes.xml" not in archive.namelist()


def test_footnotes_part_has_separator_entries(tmp_path: Path) -> None:
    """Word 要求脚注部件里有分隔符条目（id 0/1 或 -1/0）。"""
    data = render_docx_bytes(parse_dfm("正文[[fn:脚注]]\n"), _config(tmp_path))
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        footnotes = archive.read("word/footnotes.xml").decode("utf-8")
    assert "separator" in footnotes


def test_image_block_with_dimensions_renders() -> None:
    """IR 直接给尺寸（不依赖 config）。"""
    block = ImageBlock(src="pics/photo.png", alt="", width="2cm", align="right", source_line=1)
    assert block.width == "2cm"

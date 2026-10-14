"""分节 / 页码 / 页眉页脚 / 封面契约（完整版手册 W5）。

- ``[[sections]]`` 描述分节：纸张、页边距、页码体系、页眉页脚、封面
- 页码：前置罗马 + 正文阿拉伯 + 重启（``w:pgNumType`` + ``PAGE`` 域）
- 页眉页脚：每个节独立（``is_linked_to_previous = False``）
- 封面：垂直居中走 ``sectPr`` 的 ``w:vAlign``
"""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

from docgen.config import Config, load_config
from docgen.parser.dfm import parse_dfm
from docgen.render.docx import render_docx_bytes

BASE = """\
config_version = "0.1"

[math]
engine = "plain"
"""

SECTIONS = (
    BASE
    + """
[[sections]]
page.size = "A4"
page.margin.top = 2.5
page.margin.bottom = 2.5
page.margin.left = 3.0
page.margin.right = 2.5
numbering.format = "upperRoman"
header.text = "封面"
footer.text = ""

[[sections]]
page.size = "A4"
page.margin.top = 2.0
page.margin.bottom = 2.0
page.margin.left = 2.5
page.margin.right = 2.5
numbering.format = "decimal"
numbering.start = 1
header.text = "DocGen 报告"
footer.text = "第 PAGE 页"
"""
)


def _config(tmp_path: Path, text: str = SECTIONS) -> Config:
    path = tmp_path / "config.toml"
    path.write_text(text, encoding="utf-8")
    return load_config(path)


def _parts(tmp_path: Path, markdown: str, text: str = SECTIONS) -> dict[str, bytes]:
    data = render_docx_bytes(parse_dfm(markdown), _config(tmp_path, text))
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def _document_xml(tmp_path: Path, markdown: str, text: str = SECTIONS) -> str:
    return _parts(tmp_path, markdown, text)["word/document.xml"].decode("utf-8")


SAMPLE = "# 第一章\n\n正文。\n\n# 第二章\n\n第二段。\n"


# --------------------------------------------------------------------------
# 分节
# --------------------------------------------------------------------------
def test_two_sections_are_created(tmp_path: Path) -> None:
    document = _document_xml(tmp_path, SAMPLE)
    assert document.count("<w:sectPr") >= 2


def test_section_page_size_and_margins(tmp_path: Path) -> None:
    """A4 = 11906x16838 twips；页边距按 cm 换算（1cm = 567 twips）。"""
    document = _document_xml(tmp_path, SAMPLE)
    from docx.shared import Cm

    a4_width = 11906
    assert f'w:w="{a4_width}"' in document
    margins = [int(m) for m in re.findall(r'w:top="(\d+)"', document)]
    assert margins
    expected_top = int(Cm(2.0)) // 635  # 第二（正文）节
    assert any(abs(value - expected_top) <= 2 for value in margins)


def test_section_config_read_from_extra(tmp_path: Path) -> None:
    config = _config(tmp_path)
    sections = config.extra.get("sections")
    assert isinstance(sections, list) and len(sections) == 2
    assert sections[0]["numbering"]["format"] == "upperRoman"


# --------------------------------------------------------------------------
# 页码体系
# --------------------------------------------------------------------------
def test_page_numbering_format_and_restart(tmp_path: Path) -> None:
    document = _document_xml(tmp_path, SAMPLE)
    assert "<w:pgNumType" in document
    assert 'w:fmt="upperRoman"' in document
    assert 'w:fmt="decimal"' in document
    assert 'w:start="1"' in document


def test_page_number_field_in_footer(tmp_path: Path) -> None:
    parts = _parts(tmp_path, SAMPLE)
    footer_names = [name for name in parts if "footer" in name]
    assert footer_names, "没有生成页脚部件"
    assert any(b"PAGE" in parts[name] for name in footer_names)


# --------------------------------------------------------------------------
# 页眉页脚
# --------------------------------------------------------------------------
def test_header_and_footer_parts_are_created(tmp_path: Path) -> None:
    parts = _parts(tmp_path, SAMPLE)
    assert [n for n in parts if re.search(r"header\d*\.xml", n)]
    assert [n for n in parts if re.search(r"footer\d*\.xml", n)]


def test_header_text_is_written(tmp_path: Path) -> None:
    parts = _parts(tmp_path, SAMPLE)
    headers = [parts[name] for name in parts if re.search(r"header\d*\.xml", name)]
    assert any("DocGen 报告".encode() in data for data in headers)


def test_sections_are_not_linked_to_previous(tmp_path: Path) -> None:
    """正文节必须独立（``is_linked_to_previous = False``），否则页眉页脚会继承错乱。

    表现：每节都有自己的 ``sectPr``（分节符），且页眉页脚部件挂在文档关系里。
    """
    document = _document_xml(tmp_path, SAMPLE)
    assert document.count("<w:sectPr") >= 2  # 中间的分节符 + 文档末尾的节属性
    parts = _parts(tmp_path, SAMPLE)
    rels = parts["word/_rels/document.xml.rels"].decode("utf-8")
    assert "header" in rels and "footer" in rels


def test_cover_section_has_vertical_alignment(tmp_path: Path) -> None:
    """封面垂直居中：``sectPr`` 的 ``w:vAlign``。"""
    text = SECTIONS.replace('header.text = "封面"', 'header.text = "封面"\ncover = true')
    document = _document_xml(tmp_path, SAMPLE, text)
    assert '<w:vAlign w:val="center"/>' in document


# --------------------------------------------------------------------------
# 空配置不生成多余部件
# --------------------------------------------------------------------------
def test_no_sections_config_keeps_default(tmp_path: Path) -> None:
    parts = _parts(tmp_path, SAMPLE, BASE)
    assert not [n for n in parts if re.search(r"header\d*\.xml", n)]
    assert not [n for n in parts if re.search(r"footer\d*\.xml", n)]
    assert b"sectPr" in parts["word/document.xml"]


def test_sections_without_text_do_not_add_header_parts(tmp_path: Path) -> None:
    text = BASE + '\n[[sections]]\npage.size = "A4"\n'
    parts = _parts(tmp_path, SAMPLE, text)
    assert not [n for n in parts if re.search(r"header\d*\.xml", n)]

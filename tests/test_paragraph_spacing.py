"""段落间距（段前/段后）必须可配置，且单位要分得清。

反馈症状：``space_before`` / ``space_after`` 写了不报错但**静默不生效**，
于是表格底线与正文紧贴。学术排版常要求图表与正文隔 6pt / 0.5 行 / 1 行。

单位：
- 磅/绝对长度 → ``w:before`` / ``w:after``（twips，1pt = 20）；
- 行 → ``w:beforeLines`` / ``w:afterLines``（百分之一行：0.5 行 = 50）。
"""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

import pytest

from docgen.config import Config, load_config
from docgen.errors import DocGenError
from docgen.parser.dfm import parse_dfm
from docgen.render.docx import render_docx_bytes

FIXTURES = Path(__file__).parent / "fixtures"
BASE = 'config_version = "0.1"\n\n[math]\nengine = "plain"\n'


def _config(tmp_path: Path, extra: str = "") -> Config:
    path = tmp_path / "config.toml"
    path.write_text(BASE + extra, encoding="utf-8")
    return load_config(path)


def _render(tmp_path: Path, markdown: str, extra: str = "") -> str:
    data = render_docx_bytes(parse_dfm(markdown), _config(tmp_path, extra), base_dir=FIXTURES)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return archive.read("word/document.xml").decode("utf-8")


def _paragraph_spacing(document: str, text: str) -> str:
    """取包含 ``text`` 的段落的 ``w:spacing`` 开标签。"""
    for paragraph in re.findall(r"<w:p>.*?</w:p>|<w:p [^>]*>.*?</w:p>", document, re.DOTALL):
        if text in paragraph:
            match = re.search(r"<w:spacing[^>]*>", paragraph)
            return match.group(0) if match else ""
    return ""


# --------------------------------------------------------------------------
# 正文 / 文档默认值 / 覆盖
# --------------------------------------------------------------------------
def test_body_space_before_and_after_in_points(tmp_path: Path) -> None:
    document = _render(
        tmp_path, "正文。\n", '\n[styles.body]\nspace_before = "6pt"\nspace_after = "12pt"\n'
    )
    spacing = _paragraph_spacing(document, "正文")
    assert 'w:before="120"' in spacing
    assert 'w:after="240"' in spacing


def test_document_spacing_is_the_fallback(tmp_path: Path) -> None:
    document = _render(
        tmp_path, "正文。\n", '\n[document]\nspace_before = "6pt"\nspace_after = "6pt"\n'
    )
    spacing = _paragraph_spacing(document, "正文")
    assert 'w:before="120"' in spacing and 'w:after="120"' in spacing


def test_body_spacing_overrides_document(tmp_path: Path) -> None:
    extra = '\n[document]\nspace_before = "12pt"\n\n[styles.body]\nspace_before = "3pt"\n'
    document = _render(tmp_path, "正文。\n", extra)
    assert 'w:before="60"' in _paragraph_spacing(document, "正文")


def test_bare_number_is_points(tmp_path: Path) -> None:
    document = _render(tmp_path, "正文。\n", "\n[styles.body]\nspace_before = 6\n")
    assert 'w:before="120"' in _paragraph_spacing(document, "正文")


@pytest.mark.parametrize(("value", "expected"), [("12px", 180), ("0.2cm", 113)])
def test_length_units_are_converted_to_twips(tmp_path: Path, value: str, expected: int) -> None:
    """``12px`` = 9pt = 180 twips；``0.2cm`` ≈ 5.67pt ≈ 113 twips。"""
    document = _render(tmp_path, "正文。\n", f'\n[styles.body]\nspace_after = "{value}"\n')
    match = re.search(r'w:after="(\d+)"', _paragraph_spacing(document, "正文"))
    assert match is not None
    actual = int(match.group(1))
    assert abs(actual - expected) <= 2, actual


# --------------------------------------------------------------------------
# 行单位
# --------------------------------------------------------------------------
def test_line_units_use_before_after_lines(tmp_path: Path) -> None:
    document = _render(
        tmp_path, "正文。\n", '\n[styles.body]\nspace_before = "1 line"\nspace_after = "0.5 line"\n'
    )
    spacing = _paragraph_spacing(document, "正文")
    assert 'w:beforeLines="100"' in spacing
    assert 'w:afterLines="50"' in spacing


def test_chinese_line_unit_also_works(tmp_path: Path) -> None:
    document = _render(tmp_path, "正文。\n", '\n[styles.body]\nspace_before = "2行"\n')
    assert 'w:beforeLines="200"' in _paragraph_spacing(document, "正文")


def test_invalid_spacing_value_raises_config_error(tmp_path: Path) -> None:
    """写错单位要**报错**，不能静默丢掉——「写了不生效」正是这次要消灭的问题。"""
    config = _config(tmp_path, '\n[styles.body]\nspace_before = "6 banana"\n')
    with pytest.raises(DocGenError) as caught:
        render_docx_bytes(parse_dfm("正文。\n"), config)
    assert caught.value.code == "E5001"


# --------------------------------------------------------------------------
# 标题 / 题注
# --------------------------------------------------------------------------
def test_heading_spacing_from_style(tmp_path: Path) -> None:
    document = _render(
        tmp_path,
        "# 标题\n\n正文。\n",
        '\n[styles.heading1]\nspace_before = "1 line"\nspace_after = "6pt"\n',
    )
    spacing = _paragraph_spacing(document, "标题")
    assert 'w:beforeLines="100"' in spacing
    assert 'w:after="120"' in spacing


def test_heading_does_not_inherit_body_indent_or_line_spacing(tmp_path: Path) -> None:
    """标题只吃「对齐 + 段距」：不该继承正文的首行缩进与行距。"""
    extra = "\n[styles.body]\nfirst_line_chars = 200\nline_spacing = 2.0\n"
    document = _render(tmp_path, "# 标题\n\n正文。\n", extra)
    heading = next(p for p in re.findall(r"<w:p>.*?</w:p>", document, re.DOTALL) if "标题" in p)
    assert "firstLineChars" not in heading
    assert 'w:line="480"' not in heading


def test_caption_spacing_from_style(tmp_path: Path) -> None:
    markdown = "\\begin{caption #fig:1}\n图题\n\\end{caption}\n"
    document = _render(
        tmp_path, markdown, '\n[styles.caption]\nspace_before = "6pt"\nspace_after = "6pt"\n'
    )
    spacing = _paragraph_spacing(document, "图题")
    assert 'w:before="120"' in spacing and 'w:after="120"' in spacing


# --------------------------------------------------------------------------
# 表格相邻段落（Word 表格没有段距属性，写到相邻段落上）
# --------------------------------------------------------------------------
TABLE_DOC = "前文。\n\n| a | b |\n| --- | --- |\n| 1 | 2 |\n\n表后正文。\n"


def test_table_space_after_goes_to_following_paragraph(tmp_path: Path) -> None:
    document = _render(tmp_path, TABLE_DOC, '\n[table]\nspace_after = "12pt"\n')
    assert 'w:before="240"' in _paragraph_spacing(document, "表后正文")


def test_table_space_before_goes_to_preceding_paragraph(tmp_path: Path) -> None:
    document = _render(tmp_path, TABLE_DOC, '\n[table]\nspace_before = "12pt"\n')
    assert 'w:after="240"' in _paragraph_spacing(document, "前文")


def test_table_spacing_does_not_leak_to_far_paragraphs(tmp_path: Path) -> None:
    markdown = "前文。\n\n| a |\n| --- |\n| 1 |\n\n表后正文。\n\n更后面的正文。\n"
    document = _render(tmp_path, markdown, '\n[table]\nspace_after = "12pt"\n')
    assert 'w:before="240"' not in _paragraph_spacing(document, "更后面的正文")


# --------------------------------------------------------------------------
# 图片 / 行内样式
# --------------------------------------------------------------------------
def test_image_spacing_from_image_section(tmp_path: Path) -> None:
    document = _render(
        tmp_path,
        "[[img:pics/photo.png width=2cm]]\n",
        '\n[image]\nspace_before = "0.5 line"\nspace_after = "6pt"\n',
    )
    image_paragraph = next(
        (p for p in re.findall(r"<w:p>.*?</w:p>", document, re.DOTALL) if "blip" in p), ""
    )
    spacing = re.search(r"<w:spacing[^>]*>", image_paragraph)
    assert spacing is not None
    assert "beforeLines" in spacing.group(0) and 'w:after="120"' in spacing.group(0)


def test_inline_style_can_set_paragraph_spacing(tmp_path: Path) -> None:
    extra = '\n[styles.gap]\nspace_before = "6pt"\n'
    document = _render(tmp_path, "[带间距的一段]{.gap}\n", extra)
    assert 'w:before="120"' in _paragraph_spacing(document, "带间距的一段")

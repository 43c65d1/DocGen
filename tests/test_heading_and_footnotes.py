"""用户实测报告的三项：标题缩进可配、脚注自动编号、脚注文本格式。"""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

import pytest

from docgen.config import Config, load_config
from docgen.parser.dfm import parse_dfm
from docgen.render.docx import render_docx_bytes
from docgen.render.ooxml_check import validate_with_schema

BASE = 'config_version = "0.1"\n'

FOOTNOTE_MD = "正文带脚注[[fn:第一条脚注]]，还有[[fn:第二条脚注]]。\n"


def _render(tmp_path: Path, markdown: str, config_text: str = BASE) -> dict[str, bytes]:
    path = tmp_path / "config.toml"
    path.write_text(config_text, encoding="utf-8")
    data = render_docx_bytes(parse_dfm(markdown), load_config(path))
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def _xml(parts: dict[str, bytes], name: str = "word/document.xml") -> str:
    return parts[name].decode("utf-8")


# ==========================================================================
# 一、标题缩进可配
# ==========================================================================
def _level0_indent(numbering: str) -> str:
    segment = numbering.split('<w:lvl w:ilvl="0"')[1].split("</w:lvl>")[0]
    found = re.findall(r"<w:ind[^>]*/>", segment)
    return found[0] if found else ""


def _heading1_indent(styles: str) -> str:
    match = re.search(r'w:styleId="Heading1".*?</w:style>', styles, re.DOTALL)
    if match is None:
        return ""
    found = re.findall(r"<w:ind[^>]*/>", match.group(0))
    return found[0] if found else ""


def test_heading_indent_default_is_720_hanging(tmp_path: Path) -> None:
    """不配置时保持原有观感（left=720 + hanging=360）。"""
    parts = _render(tmp_path, "# 一\n")
    assert (
        _level0_indent(_xml(parts, "word/numbering.xml")) == '<w:ind w:left="720" w:hanging="360"/>'
    )
    assert (
        _heading1_indent(_xml(parts, "word/styles.xml")) == '<w:ind w:left="720" w:hanging="360"/>'
    )


def test_heading_indent_can_be_disabled_by_false(tmp_path: Path) -> None:
    """``heading_indent = false`` → 标题**无缩进**（编号定义与样式都不写 w:ind）。"""
    parts = _render(tmp_path, "# 一\n", BASE + "\n[document]\nheading_indent = false\n")
    assert _level0_indent(_xml(parts, "word/numbering.xml")) == ""
    assert _heading1_indent(_xml(parts, "word/styles.xml")) == ""


def test_heading_indent_zero_units(tmp_path: Path) -> None:
    """显式 ``left = 0`` 等价于取消缩进。"""
    parts = _render(tmp_path, "# 一\n", BASE + "\n[document]\nheading_indent.left = 0\n")
    assert _heading1_indent(_xml(parts, "word/styles.xml")) == ""


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("1cm", 567),
        ("10mm", 567),
        ("0.5in", 720),
        ("24pt", 480),
        (720, 720),
    ],
)
def test_heading_indent_accepts_units(tmp_path: Path, value: object, expected: int) -> None:
    literal = f'"{value}"' if isinstance(value, str) else str(value)
    config = BASE + f"\n[document]\nheading_indent.left = {literal}\n"
    parts = _render(tmp_path, "# 一\n", config)
    assert _heading1_indent(_xml(parts, "word/styles.xml")) == f'<w:ind w:left="{expected}"/>'


def test_heading_indent_accepts_chars(tmp_path: Path) -> None:
    """字符单位（与中文排版一致）：``leftChars`` / ``firstLineChars``。"""
    parts = _render(tmp_path, "# 一\n", BASE + "\n[document]\nheading_indent.leftChars = 200\n")
    assert _heading1_indent(_xml(parts, "word/styles.xml")) == '<w:ind w:leftChars="200"/>'

    parts = _render(
        tmp_path, "# 一\n", BASE + "\n[document]\nheading_indent.firstLineChars = 200\n"
    )
    assert _heading1_indent(_xml(parts, "word/styles.xml")) == '<w:ind w:firstLineChars="200"/>'


def test_style_level_indent_overrides_document(tmp_path: Path) -> None:
    """``[styles.heading1] indent = false`` 只影响这一级。"""
    parts = _render(tmp_path, "# 一\n\n## 二\n", BASE + "\n[styles.heading1]\nindent = false\n")
    styles = _xml(parts, "word/styles.xml")
    assert _heading1_indent(styles) == ""
    heading2 = re.search(r'w:styleId="Heading2".*?</w:style>', styles, re.DOTALL)
    assert heading2 is not None
    # Heading2 走 document 默认（未配置 → 720/hanging）
    assert 'w:left="720"' in heading2.group(0)


def test_heading_indent_first_line_drops_hanging(tmp_path: Path) -> None:
    """``firstLine`` 与 ``hanging`` 在 schema 里互斥：同时给会被自动丢弃 hanging。"""
    config = (
        BASE + '\n[document]\nheading_indent.left = "1cm"\nheading_indent.first_line = "0.5cm"\n'
    )
    parts = _render(tmp_path, "# 一\n", config)
    indent = _heading1_indent(_xml(parts, "word/styles.xml"))
    assert "firstLine=" in indent
    assert "hanging" not in indent


def test_heading_indent_is_schema_valid(tmp_path: Path) -> None:
    """加了 ``w:ind`` 之后结构仍然合法（顺序/互斥都由 schema 把关）。"""
    config = BASE + '\n[document]\nheading_indent.left = "2cm"\nheading_indent.hanging = "0.5cm"\n'
    parts = _render(tmp_path, "# 一\n\n## 二\n", config)
    assert validate_with_schema(parts["word/document.xml"]) == []


def test_heading_indent_does_not_break_outline_level(tmp_path: Path) -> None:
    """缩进改动不该影响 ``outlineLvl``（目录与导航窗格依赖它）。"""
    parts = _render(tmp_path, "# 一\n", BASE + "\n[document]\nheading_indent = false\n")
    styles = _xml(parts, "word/styles.xml")
    heading1 = re.search(r'w:styleId="Heading1".*?</w:style>', styles, re.DOTALL)
    assert heading1 is not None and "outlineLvl" in heading1.group(0)


# ==========================================================================
# 二、脚注自动编号
# ==========================================================================
def test_footnote_entry_has_footnote_ref(tmp_path: Path) -> None:
    """回归：条目里必须有 ``w:footnoteRef``（Word 的自动编号占位）。

    缺了它就只显示文本、不编号——用户实测报的正是这个。
    """
    parts = _render(tmp_path, FOOTNOTE_MD)
    footnotes = _xml(parts, "word/footnotes.xml")
    assert footnotes.count("<w:footnoteRef/>") == 2


def test_footnote_references_in_body(tmp_path: Path) -> None:
    document = _xml(_render(tmp_path, FOOTNOTE_MD))
    assert document.count("footnoteReference") == 2
    assert '<w:footnoteReference w:id="1"/>' in document
    assert '<w:footnoteReference w:id="2"/>' in document


def test_footnote_ids_match_between_body_and_part(tmp_path: Path) -> None:
    parts = _render(tmp_path, FOOTNOTE_MD)
    document = _xml(parts)
    footnotes = _xml(parts, "word/footnotes.xml")
    body_ids = re.findall(r'<w:footnoteReference w:id="(\d+)"/>', document)
    entry_ids = re.findall(r'<w:footnote w:id="(\d+)">', footnotes)
    assert body_ids == entry_ids == ["1", "2"]


def test_footnote_part_has_separators(tmp_path: Path) -> None:
    footnotes = _xml(_render(tmp_path, FOOTNOTE_MD), "word/footnotes.xml")
    assert 'w:type="separator"' in footnotes
    assert 'w:type="continuationSeparator"' in footnotes


def test_footnote_ids_are_unique_across_document(tmp_path: Path) -> None:
    """多个脚注的 id 必须唯一，否则 Word 会串号。"""
    footnotes = _xml(_render(tmp_path, FOOTNOTE_MD), "word/footnotes.xml")
    ids = re.findall(r'<w:footnote w:id="(-?\d+)"', footnotes)
    assert len(ids) == len(set(ids))


# ==========================================================================
# 三、脚注文本格式：不再整体上标、行距收敛
# ==========================================================================
def test_footnote_text_is_not_superscript(tmp_path: Path) -> None:
    """回归：整条脚注文本曾被加 ``vertAlign=superscript``（用户实测报的）。"""
    parts = _render(tmp_path, FOOTNOTE_MD)
    footnotes = _xml(parts, "word/footnotes.xml")
    entry = re.search(r'<w:footnote w:id="1">.*?</w:footnote>', footnotes, re.DOTALL)
    assert entry is not None
    body = entry.group(0)
    # 只有编号 run（带 footnoteRef）可以上标；文本 run 不允许
    text_runs = re.findall(r"<w:r>(?:(?!</w:r>).)*?</w:r>", body, re.DOTALL)
    text_only = [run for run in text_runs if "footnoteRef" not in run]
    assert text_only, "应该有纯文本 run"
    for run in text_only:
        assert "vertAlign" not in run, run


def test_footnote_reference_run_is_superscript(tmp_path: Path) -> None:
    """编号那一个 run 仍应是上标，并用 FootnoteReference 字符样式。"""
    parts = _render(tmp_path, FOOTNOTE_MD)
    footnotes = _xml(parts, "word/footnotes.xml")
    entry = re.search(r'<w:footnote w:id="1">.*?</w:footnote>', footnotes, re.DOTALL)
    assert entry is not None
    reference_runs = [
        run
        for run in re.findall(r"<w:r>(?:(?!</w:r>).)*?</w:r>", entry.group(0), re.DOTALL)
        if "footnoteRef" in run
    ]
    assert reference_runs
    assert "FootnoteReference" in reference_runs[0]
    assert 'w:val="superscript"' in reference_runs[0]


def test_footnote_text_has_single_line_spacing(tmp_path: Path) -> None:
    """脚注默认单倍行距（240 twips），不再跟随正文 1.4 倍显得松散。"""
    parts = _render(tmp_path, FOOTNOTE_MD, BASE + "\n[document]\nline_spacing = 1.4\n")
    footnotes = _xml(parts, "word/footnotes.xml")
    entry = re.search(r'<w:footnote w:id="1">.*?</w:footnote>', footnotes, re.DOTALL)
    assert entry is not None
    assert 'w:line="240"' in entry.group(0)
    assert 'w:lineRule="auto"' in entry.group(0)


def test_footnote_line_spacing_configurable(tmp_path: Path) -> None:
    """``[styles.footnote] line_spacing`` 可改脚注行距。"""
    config = BASE + "\n[styles.footnote]\nline_spacing = 1.5\n"
    parts = _render(tmp_path, FOOTNOTE_MD, config)
    footnotes = _xml(parts, "word/footnotes.xml")
    assert 'w:line="360"' in footnotes  # 1.5 * 240


def test_footnote_entry_uses_footnote_text_style(tmp_path: Path) -> None:
    parts = _render(tmp_path, FOOTNOTE_MD)
    footnotes = _xml(parts, "word/footnotes.xml")
    assert 'w:val="FootnoteText"' in footnotes


def test_footnotes_xml_is_schema_valid(tmp_path: Path) -> None:
    """脚注部件也要过官方 schema（它能抓出元素顺序与非法取值）。

    这条测试是**真实收益**：它抓出了 ``w:br w:type="separator"`` 的非法取值
    （``ST_BrType`` 只允许 page/column/textWrapping），正确写法是 ``w:separator`` 元素。
    """
    from lxml import etree

    from docgen.render.ooxml_check import wml_schema

    schema = wml_schema()
    parts = _render(tmp_path, FOOTNOTE_MD)
    assert schema.validate(etree.fromstring(parts["word/footnotes.xml"])), [
        str(err) for err in schema.error_log
    ][:3]


def test_no_footnotes_no_part(tmp_path: Path) -> None:
    parts = _render(tmp_path, "普通段落\n")
    assert "word/footnotes.xml" not in parts


def test_footnote_text_content_preserved(tmp_path: Path) -> None:
    footnotes = _xml(_render(tmp_path, FOOTNOTE_MD), "word/footnotes.xml")
    assert "第一条脚注" in footnotes
    assert "第二条脚注" in footnotes


def test_heading_indent_helper_semantics() -> None:
    """``heading_indent`` 的三态：未配置 / false / 子表。"""
    from docgen.render.template import heading_indent

    def config(document: dict[str, object]) -> Config:
        return Config(
            version="0.1", document=document, styles={}, code_block={}, code_blocks={}, raw={}
        )

    assert heading_indent(config({})) is None
    assert heading_indent(config({"heading_indent": False})) == {}
    assert heading_indent(config({"heading_indent": {"left": "1cm"}})) == {"left": "1cm"}
    assert heading_indent(config({"heading_indent.left": "1cm"})) == {"left": "1cm"}
    assert heading_indent(config({"heading_indent": "2cm"})) == {"left": "2cm"}

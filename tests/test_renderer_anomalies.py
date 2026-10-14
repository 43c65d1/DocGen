"""用户实测报告的三项行为契约。

1. ``---`` 分隔线应是**段落底边框**，不是一长串破折号
2. 标题多级编号要能**关掉**（``[document] heading_numbering``）
3. 页面垂直对齐**每节显式设置**（封面 center / 正文 top），不依赖「克隆后删除」
"""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path
from typing import Any

import pytest

from docgen.config import Config, load_config
from docgen.parser.dfm import parse_dfm
from docgen.render.docx import render_docx_bytes

BASE = 'config_version = "0.1"\n\n[math]\nengine = "plain"\n'


def _render(tmp_path: Path, markdown: str, config_text: str = BASE) -> str:
    path = tmp_path / "config.toml"
    path.write_text(config_text, encoding="utf-8")
    data = render_docx_bytes(parse_dfm(markdown), load_config(path))
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return archive.read("word/document.xml").decode("utf-8")


# --------------------------------------------------------------------------
# 1. 分隔线
# --------------------------------------------------------------------------
def test_thematic_break_uses_paragraph_border(tmp_path: Path) -> None:
    """``---`` → 空段落 + ``w:pBdr/w:bottom``，产物里不该有一串破折号。"""
    document = _render(tmp_path, "上文。\n\n---\n\n下文。\n")
    assert "<w:pBdr>" in document
    assert '<w:bottom w:val="single"' in document
    assert "———" not in document
    assert "\u2014\u2014\u2014" not in document


def test_thematic_break_border_is_configurable(tmp_path: Path) -> None:
    config = BASE + '\n[document]\nhr.style = "double"\nhr.size = "12"\nhr.color = "FF0000"\n'
    document = _render(tmp_path, "上文。\n\n---\n\n下文。\n", config)
    assert 'w:val="double"' in document
    assert 'w:sz="12"' in document
    assert 'w:color="FF0000"' in document


def test_thematic_break_border_color_auto_stays_lowercase(tmp_path: Path) -> None:
    """``auto`` 必须小写：``w:ST_HexColor`` 只认小写 auto（大写会被 schema 拒）。"""
    document = _render(tmp_path, "---\n")
    assert 'w:color="auto"' in document
    assert 'w:color="AUTO"' not in document


def test_paragraph_text_has_no_border(tmp_path: Path) -> None:
    """普通段落不该被加上底边框。"""
    document = _render(tmp_path, "普通段落。\n")
    assert "<w:pBdr>" not in document


# --------------------------------------------------------------------------
# 2. 标题编号开关
# --------------------------------------------------------------------------
def test_heading_numbering_on_by_default(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text(BASE, encoding="utf-8")
    data = render_docx_bytes(parse_dfm("# 标题\n\n正文\n"), load_config(path))
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        styles = archive.read("word/styles.xml").decode("utf-8")
        numbering = archive.read("word/numbering.xml").decode("utf-8")
    assert '<w:numId w:val="100"/>' in styles  # HeadingN 绑定了编号
    assert 'w:abstractNumId="100"' in numbering


def test_heading_numbering_can_be_disabled(tmp_path: Path) -> None:
    """``heading_numbering = false`` → 标题**不**绑编号，但 outlineLvl 仍在（目录照常）。"""
    path = tmp_path / "config.toml"
    path.write_text(BASE + "\n[document]\nheading_numbering = false\n", encoding="utf-8")
    data = render_docx_bytes(parse_dfm("# 标题\n\n正文\n"), load_config(path))
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        styles = archive.read("word/styles.xml").decode("utf-8")
    heading1 = re.search(r'w:styleId="Heading1".*?</w:style>', styles, re.DOTALL)
    assert heading1 is not None
    assert "w:numPr" not in heading1.group(0), "关闭编号后 Heading1 不该再有 numPr"
    assert "outlineLvl" in heading1.group(0), "outlineLvl 与编号无关，必须保留"


def test_heading_numbering_accepts_nested_form(tmp_path: Path) -> None:
    """``heading_numbering.enabled``（点号/子表写法）同样生效。"""
    path = tmp_path / "config.toml"
    path.write_text(BASE + "\n[document]\nheading_numbering.enabled = false\n", encoding="utf-8")
    data = render_docx_bytes(parse_dfm("# 标题\n"), load_config(path))
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        styles = archive.read("word/styles.xml").decode("utf-8")
    heading1 = re.search(r'w:styleId="Heading1".*?</w:style>', styles, re.DOTALL)
    assert heading1 is not None and "w:numPr" not in heading1.group(0)


def test_numbering_toggle_helper() -> None:
    from docgen.render.template import heading_numbering_enabled

    def config(document: dict[str, Any]) -> Config:
        return Config(
            version="0.1", document=document, styles={}, code_block={}, code_blocks={}, raw={}
        )

    assert heading_numbering_enabled(config({})) is True
    assert heading_numbering_enabled(config({"heading_numbering": False})) is False
    assert heading_numbering_enabled(config({"heading_numbering": {"enabled": False}})) is False
    assert heading_numbering_enabled(config({"heading_numbering": {"enabled": True}})) is True


# --------------------------------------------------------------------------
# 3. 页面垂直对齐：每节显式
# --------------------------------------------------------------------------
SECTIONS = (
    BASE
    + """
[[sections]]
page.size = "A4"
cover = true

[[sections]]
page.size = "A4"
numbering.format = "decimal"
"""
)


def test_each_section_sets_v_align_explicitly(tmp_path: Path) -> None:
    """封面 center、正文 top——两节都**显式**写出来，不靠「克隆后删除」。"""
    document = _render(tmp_path, "# 封面\n\n# 正文\n", SECTIONS)
    aligns = re.findall(r'<w:vAlign w:val="(\w+)"/>', document)
    assert aligns == ["center", "top"], aligns


def test_v_align_absent_when_no_sections_config(tmp_path: Path) -> None:
    """没配 ``[[sections]]`` 时不主动写 vAlign（保持母版默认）。"""
    document = _render(tmp_path, "# 标题\n")
    assert "<w:vAlign" not in document


@pytest.mark.parametrize("value", ["center", "top"])
def test_v_align_is_schema_ordered(tmp_path: Path, value: str) -> None:
    """``w:vAlign`` 必须排在 ``w:docGrid`` 之前（insert_child 负责）。"""
    document = _render(tmp_path, "# 一\n\n# 二\n", SECTIONS)
    assert document.index("<w:vAlign") < document.index("<w:docGrid")

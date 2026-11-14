"""中文字号（号数制）→ 磅值：Word/WPS 同口径的换算表。"""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

import pytest

from docgen.config import load_config
from docgen.errors import DocGenError
from docgen.parser.dfm import parse_dfm
from docgen.render.docx import render_docx_bytes
from docgen.units import CN_FONT_SIZES, to_points

BASE = 'config_version = "0.1"\n\n[document]\nfont.name = "宋体"\n'


def _render(tmp_path: Path, markdown: str = "正文。\n", extra: str = "") -> tuple[str, str]:
    path = tmp_path / "c.toml"
    path.write_text(BASE + extra, encoding="utf-8")
    data = render_docx_bytes(parse_dfm(markdown), load_config(path), base_dir=tmp_path)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return archive.read("word/document.xml").decode("utf-8"), archive.read(
            "word/styles.xml"
        ).decode("utf-8")


# --------------------------------------------------------------------------
# 换算表
# --------------------------------------------------------------------------
@pytest.mark.parametrize(("name", "points"), list(CN_FONT_SIZES.items()))
def test_all_mappings(name: str, points: float) -> None:
    assert to_points(name).pt == pytest.approx(points)


@pytest.mark.parametrize(
    ("value", "points"),
    [
        ("小四号", 12.0),  # 带「号」后缀
        ("四号", 14.0),
        ("三号", 16.0),
        ("小五号", 9.0),
        ("12磅", 12.0),
        ("12pt", 12.0),
        (12, 12.0),
    ],
)
def test_aliases(value: object, points: float) -> None:
    assert to_points(value).pt == pytest.approx(points)


@pytest.mark.parametrize("value", ["小十", "abc", "", True, "小四cm"])
def test_invalid_size_raises_e5001(value: object) -> None:
    with pytest.raises(DocGenError) as caught:
        to_points(value)
    assert caught.value.code == "E5001"


@pytest.mark.parametrize("name", ["初号", "小初", "一号", "小一", "二号", "小二", "三号", "小三"])
def test_known_names_are_stable(name: str) -> None:
    """这些是高校规范最常用的标题字号，映射不能漂。"""
    assert name in CN_FONT_SIZES


# --------------------------------------------------------------------------
# 渲染：document / heading / inline / table.text
# --------------------------------------------------------------------------
def test_document_font_size_in_cn(tmp_path: Path) -> None:
    _, styles = _render(tmp_path, extra='\nfont.size = "小四"\n')
    normal = re.search(r'w:styleId="Normal".*?</w:style>', styles, re.DOTALL)
    assert normal is not None
    assert 'w:sz w:val="24"' in normal.group(0)  # 12pt


def test_heading_font_size_in_cn(tmp_path: Path) -> None:
    _, styles = _render(
        tmp_path, markdown="# 标题\n", extra='\n[styles.heading1]\nfont.size = "三号"\n'
    )
    heading = re.search(r'w:styleId="Heading1".*?</w:style>', styles, re.DOTALL)
    assert heading is not None
    assert 'w:sz w:val="32"' in heading.group(0)  # 16pt


def test_inline_style_font_size_in_cn(tmp_path: Path) -> None:
    document, _ = _render(
        tmp_path,
        markdown="**粗体**\n",
        extra='\n[styles.strong]\nfont.size = "小五"\nfont.bold = true\n',
    )
    assert 'w:sz w:val="18"' in document  # 9pt


def test_table_text_font_size_in_cn(tmp_path: Path) -> None:
    document, _ = _render(
        tmp_path,
        markdown="| a |\n| --- |\n| 1 |\n",
        extra='\n[table.text]\nfont.size = "五号"\n',
    )
    cell = re.search(r"<w:tc>.*?</w:tc>", document, re.DOTALL)
    assert cell is not None
    assert 'w:sz w:val="21"' in cell.group(0)  # 10.5pt


def test_unknown_font_size_is_content_error(tmp_path: Path) -> None:
    with pytest.raises(DocGenError) as caught:
        _render(tmp_path, extra='\nfont.size = "小十"\n')
    assert caught.value.code == "E5001"

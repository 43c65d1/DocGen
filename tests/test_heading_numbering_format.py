"""标题编号预设：decimal（Word 多级编号） / chapter（第一章） / chinese（一、）。"""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

import pytest

from docgen.config import Config, load_config
from docgen.errors import DocGenError
from docgen.numbering import (
    baked_heading_labels,
    format_heading_label,
    heading_numbering_mode,
)
from docgen.parser.dfm import parse_dfm
from docgen.render.docx import render_docx_bytes
from docgen.validate import validate_content

BASE = 'config_version = "0.1"\n'


def _config(tmp_path: Path, extra: str = "") -> Config:
    path = tmp_path / "c.toml"
    path.write_text(BASE + extra, encoding="utf-8")
    return load_config(path)


def _render(tmp_path: Path, markdown: str, extra: str = "") -> str:
    data = render_docx_bytes(parse_dfm(markdown), _config(tmp_path, extra), base_dir=tmp_path)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return archive.read("word/document.xml").decode("utf-8")


def _paragraph_texts(document: str) -> list[str]:
    paragraphs = re.findall(r"<w:p>.*?</w:p>", document, re.DOTALL)
    texts = []
    for paragraph in paragraphs:
        text = "".join(re.findall(r"<w:t(?: [^>]*)?>(.*?)</w:t>", paragraph, re.DOTALL))
        if text:
            texts.append(text)
    return texts


DOC = "# 绪论\n\n正文。\n\n## 研究背景\n\n### 问题定义\n\n# 方法\n"


# --------------------------------------------------------------------------
# 模式解析
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("snippet", "mode"),
    [
        ("heading_numbering = true", "decimal"),
        ("heading_numbering = false", "off"),
        ('heading_numbering = "decimal"', "decimal"),
        ('heading_numbering = "chapter"', "chapter"),
        ('heading_numbering = "chinese"', "chinese"),
        ('heading_numbering = "CHAPTER"', "chapter"),
    ],
)
def test_mode_parsing(tmp_path: Path, snippet: str, mode: str) -> None:
    assert heading_numbering_mode(_config(tmp_path, "\n[document]\n" + snippet + "\n")) == mode


def test_mode_parsing_table_forms(tmp_path: Path) -> None:
    assert (
        heading_numbering_mode(
            _config(tmp_path, '\n[document.heading_numbering]\nstyle = "chapter"\n')
        )
        == "chapter"
    )
    assert (
        heading_numbering_mode(
            _config(tmp_path, "\n[document.heading_numbering]\nenabled = false\n")
        )
        == "off"
    )


def test_invalid_mode_raises(tmp_path: Path) -> None:
    with pytest.raises(DocGenError) as caught:
        heading_numbering_mode(_config(tmp_path, '\n[document]\nheading_numbering = "uppercase"\n'))
    assert caught.value.code == "E5001"


def test_invalid_mode_reported_by_validate(tmp_path: Path) -> None:
    errors = validate_content(
        parse_dfm("# 标题\n"),
        _config(tmp_path, '\n[document]\nheading_numbering = "uppercase"\n'),
    )
    assert any(error.code == "E5001" for error in errors)


# --------------------------------------------------------------------------
# 编号文本
# --------------------------------------------------------------------------
def test_format_chapter_labels() -> None:
    assert format_heading_label("chapter", 1, [0, 1, 0]) == "第一章"
    assert format_heading_label("chapter", 2, [0, 1, 2]) == "1.2"
    assert format_heading_label("chapter", 3, [0, 1, 2, 3]) == "1.2.3"
    assert format_heading_label("chapter", 1, [0, 11, 0]) == "第十一章"


def test_format_chinese_labels() -> None:
    assert format_heading_label("chinese", 1, [0, 1, 0]) == "一、"
    assert format_heading_label("chinese", 2, [0, 1, 2]) == "（二）"
    assert format_heading_label("chinese", 3, [0, 1, 2, 3]) == "3."
    assert format_heading_label("chinese", 4, [0, 1, 2, 3, 4]) == "（4）"
    assert format_heading_label("chinese", 1, [0, 12, 0]) == "十二、"


def test_baked_labels_reset_on_higher_level(tmp_path: Path) -> None:
    blocks = parse_dfm(DOC)
    labels = baked_heading_labels(
        blocks, _config(tmp_path, '\n[document]\nheading_numbering = "chapter"\n')
    )
    values = list(labels.values())
    assert values == ["第一章", "1.1", "1.1.1", "第二章"]


def test_baked_labels_empty_for_decimal_and_off(tmp_path: Path) -> None:
    blocks = parse_dfm(DOC)
    assert baked_heading_labels(blocks, _config(tmp_path)) == {}
    assert (
        baked_heading_labels(blocks, _config(tmp_path, "\n[document]\nheading_numbering = false\n"))
        == {}
    )


# --------------------------------------------------------------------------
# 渲染
# --------------------------------------------------------------------------
def test_render_chapter(tmp_path: Path) -> None:
    document = _render(tmp_path, DOC, '\n[document]\nheading_numbering = "chapter"\n')
    assert _paragraph_texts(document)[:5] == [
        "第一章 绪论",
        "正文。",
        "1.1 研究背景",
        "1.1.1 问题定义",
        "第二章 方法",
    ]
    assert 'w:numId w:val="0"' in document  # 烘焙模式下显式清掉样式编号


def test_render_chinese(tmp_path: Path) -> None:
    document = _render(tmp_path, DOC, '\n[document]\nheading_numbering = "chinese"\n')
    assert _paragraph_texts(document)[:5] == [
        "一、绪论",
        "正文。",
        "（一）研究背景",
        "1. 问题定义",
        "二、方法",
    ]


def test_default_decimal_has_no_baked_text(tmp_path: Path) -> None:
    document = _render(tmp_path, DOC)
    texts = _paragraph_texts(document)
    assert texts[0] == "绪论"  # Word 多级编号负责显示，不在文本里
    assert texts[2] == "研究背景"


def test_heading_numbering_off_has_no_baked_text(tmp_path: Path) -> None:
    document = _render(tmp_path, DOC, "\n[document]\nheading_numbering = false\n")
    assert _paragraph_texts(document)[0] == "绪论"


def test_invalid_mode_render_raises(tmp_path: Path) -> None:
    with pytest.raises(DocGenError) as caught:
        _render(tmp_path, DOC, '\n[document]\nheading_numbering = "uppercase"\n')
    assert caught.value.code == "E5001"

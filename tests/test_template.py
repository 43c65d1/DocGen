"""母版校准（完整版手册 §14.1 / §14.3）。

只断言母版**必须存在的槽位**：样式 id 规范、标题 outlineLvl、多级编号绑定、
TOC 1..9 显式定义、四个字体属性、updateFields。这些是 W3（编号/题注）与 W5（目录）的前置。
"""

from __future__ import annotations

import io
import re
import zipfile
from typing import Any

from docx import Document

from docgen.render.template_build import (
    HEADING_NUMBER_ID,
    TOC_LEVELS,
    build_template,
    template_bytes,
)

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _parts() -> tuple[Any, str, str, str]:
    data = template_bytes()
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        styles = archive.read("word/styles.xml").decode("utf-8")
        numbering = archive.read("word/numbering.xml").decode("utf-8")
        settings = archive.read("word/settings.xml").decode("utf-8")
    return Document(io.BytesIO(data)), styles, numbering, settings


def test_engine_document_has_same_slots_as_template() -> None:
    """回归：``create_document()``（构建路径）必须和母版构建路径一样补齐槽位。

    否则 ``docgen build`` 产出的文档会缺 ``TOC 1..9``、多级编号与题注样式，
    而 W3（题注/引用）与 W5（目录）都依赖它们。
    """
    from docgen.config import Config
    from docgen.render.template import create_document

    config = Config(
        version="0.1",
        document={},
        styles={},
        code_block={},
        code_blocks={},
        raw={},
    )
    data = _save(create_document(config))
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        styles = archive.read("word/styles.xml").decode("utf-8")
        numbering = archive.read("word/numbering.xml").decode("utf-8")
        settings = archive.read("word/settings.xml").decode("utf-8")

    names = set(re.findall(r'<w:name w:val="([^"]+)"', styles))
    assert "TOC 1" in names and "TOC 9" in names
    assert any(name.lower() == "caption" for name in names)
    assert "outlineLvl" in styles
    assert f'w:abstractNumId="{HEADING_NUMBER_ID}"' in numbering
    assert f'<w:numId w:val="{HEADING_NUMBER_ID}"/>' in styles
    assert "updateFields" in settings


def _save(document: object) -> bytes:
    buffer = io.BytesIO()
    document.save(buffer)  # type: ignore[attr-defined]
    return buffer.getvalue()


def test_engine_document_is_idempotent() -> None:
    """重复创建不应重复插入编号定义。"""
    from docgen.config import Config
    from docgen.render.template import create_document

    config = Config(
        version="0.1",
        document={},
        styles={},
        code_block={},
        code_blocks={},
        raw={},
    )
    document = create_document(config)
    from docgen.render.template_build import add_heading_numbering

    add_heading_numbering(document)
    numbering = document.part.numbering_part.element
    matches = [
        element
        for element in numbering.findall(f"{_W}abstractNum")
        if element.get(f"{_W}abstractNumId") == str(HEADING_NUMBER_ID)
    ]
    assert len(matches) == 1


def test_build_template_returns_document() -> None:
    document = build_template()
    assert document is not None
    assert document.paragraphs == []


def test_toc_styles_are_defined() -> None:
    """目录必须有显式的 TOC 1..9 样式，否则目录域渲染会退化成正文。"""
    document, styles, _, _ = _parts()
    names = {style.name for style in document.styles}
    for level in TOC_LEVELS:
        assert f"TOC {level}" in names, f"缺少目录样式 TOC {level}"
        assert f'w:styleId="TOC{level}"' in styles


def test_heading_styles_have_outline_level() -> None:
    _, styles, _, _ = _parts()
    assert styles.count("outlineLvl") >= 9
    for level in range(9):
        assert f'w:val="{level}"' in styles


def test_heading_numbering_is_linked() -> None:
    """HeadingN 必须绑定 numPr(numId/ilvl)，否则标题不会自动编号。"""
    _, styles, numbering, _ = _parts()
    assert f'w:abstractNumId="{HEADING_NUMBER_ID}"' in numbering
    assert "<w:numPr>" in styles
    assert f'<w:numId w:val="{HEADING_NUMBER_ID}"/>' in styles
    for level in range(9):
        assert f'<w:ilvl w:val="{level}"/>' in styles


def test_multilevel_numbering_uses_decimal_level_text() -> None:
    _, _, numbering, _ = _parts()
    assert 'w:lvlText w:val="%1"' in numbering
    assert 'w:lvlText w:val="%1.%2"' in numbering
    assert 'w:lvlText w:val="%1.%2.%3"' in numbering


def test_numbering_is_idempotent() -> None:
    document = build_template()
    from docgen.render.template_build import add_heading_numbering

    add_heading_numbering(document)
    add_heading_numbering(document)
    numbering = document.part.numbering_part.element
    matches = [
        element
        for element in numbering.findall(f"{_W}abstractNum")
        if element.get(f"{_W}abstractNumId") == str(HEADING_NUMBER_ID)
    ]
    assert len(matches) == 1


def test_settings_enable_update_fields() -> None:
    _, _, _, settings = _parts()
    assert "updateFields" in settings


def test_toc_style_is_not_hidden_and_quick() -> None:
    document, _, _, _ = _parts()
    style = next(item for item in document.styles if item.name == "TOC 1")
    assert style.hidden is False


def test_template_bytes_is_deterministic_shape() -> None:
    first = template_bytes()
    second = template_bytes()
    with zipfile.ZipFile(io.BytesIO(first)) as left, zipfile.ZipFile(io.BytesIO(second)) as right:
        assert sorted(left.namelist()) == sorted(right.namelist())
        assert left.read("word/numbering.xml") == right.read("word/numbering.xml")


def test_existing_styles_are_not_duplicated() -> None:
    """母版已有 Caption/Body Text/List Bullet 等，不能被重复创建。"""
    document, _, _, _ = _parts()
    names = [style.name for style in document.styles]
    assert names.count("Caption") == 1
    assert names.count("Body Text") == 1
    assert names.count("TOC 1") == 1

"""标题默认颜色：母版主题蓝必须清掉（默认黑，config 可覆盖）。"""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

from docx import Document
from docx.shared import RGBColor

from docgen.config import Config, load_config
from docgen.parser.dfm import parse_dfm
from docgen.render.docx import render_docx_bytes

BASE = 'config_version = "0.1"\n'


def _config(tmp_path: Path, extra: str = "") -> Config:
    path = tmp_path / "c.toml"
    path.write_text(BASE + extra, encoding="utf-8")
    return load_config(path)


def _parts(tmp_path: Path, extra: str = "", template: Path | None = None) -> tuple[str, str]:
    data = render_docx_bytes(
        parse_dfm("# 一级标题\n\n正文。\n"),
        _config(tmp_path, extra),
        base_dir=tmp_path,
        template=template,
    )
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return (
            archive.read("word/document.xml").decode("utf-8"),
            archive.read("word/styles.xml").decode("utf-8"),
        )


def _heading_style(styles: str, style_id: str = "Heading1") -> str:
    match = re.search(rf'<w:style [^>]*w:styleId="{style_id}".*?</w:style>', styles, re.DOTALL)
    assert match is not None
    return match.group(0)


def test_default_heading_has_no_explicit_colour(tmp_path: Path) -> None:
    """默认母版的主题蓝必须清掉，否则标题是蓝色而不是黑色。"""
    document, styles = _parts(tmp_path)
    heading = _heading_style(styles)
    assert "w:color" not in heading
    assert "C00000" not in heading
    # 正文段落（标题）也不要带 run 级颜色
    assert "<w:color" not in document


def test_default_heading_keeps_size_and_bold(tmp_path: Path) -> None:
    """只清颜色：字号与加粗仍是母版默认（14pt / 加粗）。"""
    _, styles = _parts(tmp_path)
    heading = _heading_style(styles)
    assert '<w:sz w:val="28"/>' in heading
    assert "<w:b/>" in heading


def test_config_heading_colour_still_applies(tmp_path: Path) -> None:
    document, styles = _parts(tmp_path, '\n[styles.heading1]\nfont.color = "C00000"\n')
    heading = _heading_style(styles)
    assert "C00000" in heading
    assert "C00000" in document


def test_custom_template_keeps_its_colour(tmp_path: Path) -> None:
    """自定义母版保留作者配色：中性化只作用于引擎默认母版。"""
    template = tmp_path / "template.docx"
    model = Document()
    model.styles["Heading 1"].font.color.rgb = RGBColor(0x00, 0x70, 0xC0)
    model.save(str(template))
    _, styles = _parts(tmp_path, template=template)
    assert "0070C0" in _heading_style(styles)

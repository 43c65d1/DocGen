"""中文字体与西文字体分开设置（``font.name`` + ``font.latin``）。"""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

from docgen.config import Config, load_config
from docgen.parser.dfm import parse_dfm
from docgen.render.docx import render_docx_bytes

BASE = 'config_version = "0.1"\n\n[document]\nfont.name = "宋体"\n'


def _config(tmp_path: Path, extra: str = "") -> Config:
    path = tmp_path / "c.toml"
    path.write_text(BASE + extra, encoding="utf-8")
    return load_config(path)


def _render(tmp_path: Path, markdown: str, extra: str = "") -> tuple[str, str]:
    data = render_docx_bytes(parse_dfm(markdown), _config(tmp_path, extra), base_dir=tmp_path)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return archive.read("word/document.xml").decode("utf-8"), archive.read(
            "word/styles.xml"
        ).decode("utf-8")


def _style_block(styles: str, style_id: str) -> str:
    match = re.search(rf'<w:style [^>]*w:styleId="{style_id}".*?</w:style>', styles, re.DOTALL)
    return match.group(0) if match else ""


def _font_attrs(xml: str) -> dict[str, str]:
    match = re.search(r"<w:rFonts ([^/>]*)/>", xml)
    if not match:
        return {}
    return dict(re.findall(r'(w:[a-zA-Z]+)="([^"]*)"', match.group(1)))


def test_default_name_sets_all_four_attributes(tmp_path: Path) -> None:
    _, styles = _render(tmp_path, "正文。\n")
    attrs = _font_attrs(_style_block(styles, "Normal"))
    assert attrs == {
        "w:ascii": "宋体",
        "w:hAnsi": "宋体",
        "w:cs": "宋体",
        "w:eastAsia": "宋体",
    }


def test_font_latin_splits_western_and_east_asian(tmp_path: Path) -> None:
    _, styles = _render(tmp_path, "正文。\n", extra='\nfont.latin = "Times New Roman"\n')
    attrs = _font_attrs(_style_block(styles, "Normal"))
    assert attrs["w:ascii"] == "Times New Roman"
    assert attrs["w:hAnsi"] == "Times New Roman"
    assert attrs["w:cs"] == "Times New Roman"
    assert attrs["w:eastAsia"] == "宋体"


def test_heading_style_can_split_fonts(tmp_path: Path) -> None:
    _, styles = _render(
        tmp_path,
        "# 标题\n",
        extra='\n[styles.heading1]\nfont.name = "黑体"\nfont.latin = "Arial"\n',
    )
    attrs = _font_attrs(_style_block(styles, "Heading1"))
    assert attrs["w:ascii"] == "Arial"
    assert attrs["w:eastAsia"] == "黑体"


def test_inline_style_run_can_split_fonts(tmp_path: Path) -> None:
    document, _ = _render(
        tmp_path,
        "**粗体**\n",
        extra=(
            '\n[styles.strong]\nfont.name = "黑体"\nfont.latin = "Arial Bold"\nfont.bold = true\n'
        ),
    )
    run_fonts = re.findall(r"<w:rFonts [^>]*/>", document)
    assert any('w:ascii="Arial Bold"' in item and 'w:eastAsia="黑体"' in item for item in run_fonts)


def test_table_text_can_split_fonts(tmp_path: Path) -> None:
    document, _ = _render(
        tmp_path,
        "| a |\n| --- |\n| 1 |\n",
        extra='\n[table.text]\nfont.name = "宋体"\nfont.latin = "Times New Roman"\n',
    )
    cell = re.search(r"<w:tc>.*?</w:tc>", document, re.DOTALL)
    assert cell is not None
    attrs = _font_attrs(cell.group(0))
    assert attrs["w:ascii"] == "Times New Roman"
    assert attrs["w:eastAsia"] == "宋体"


def test_latin_only_keeps_east_asian_untouched(tmp_path: Path) -> None:
    config_path = tmp_path / "c.toml"
    config_path.write_text(
        'config_version = "0.1"\n\n[document]\nfont.latin = "Arial"\n', encoding="utf-8"
    )
    data = render_docx_bytes(parse_dfm("正文。\n"), load_config(config_path), base_dir=tmp_path)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        styles = archive.read("word/styles.xml").decode("utf-8")
    attrs = _font_attrs(_style_block(styles, "Normal"))
    assert attrs.get("w:ascii") == "Arial"
    assert attrs.get("w:eastAsia") is None

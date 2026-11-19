"""表格自动列宽与单行行高。"""

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

BASE = 'config_version = "0.1"\n'
DOC = """| 序号 | 说明 |
| --- | --- |
| 1 | 这是一段很长很长的说明文字，用来测试自动列宽 |
"""


def _config(tmp_path: Path, extra: str = "") -> Config:
    path = tmp_path / "c.toml"
    path.write_text(BASE + extra, encoding="utf-8")
    return load_config(path)


def _document(tmp_path: Path, extra: str = "", markdown: str = DOC) -> str:
    data = render_docx_bytes(parse_dfm(markdown), _config(tmp_path, extra), base_dir=tmp_path)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return archive.read("word/document.xml").decode("utf-8")


def _grid(document: str) -> list[int]:
    return [int(value) for value in re.findall(r'<w:gridCol w:w="(\d+)"', document)]


def test_auto_width_gives_short_column_less_space(tmp_path: Path) -> None:
    widths = _grid(_document(tmp_path, '\n[table]\ncol_widths = "auto"\n'))
    assert widths[0] < widths[1]
    assert widths[0] > 0


def test_mixed_absolute_and_auto(tmp_path: Path) -> None:
    widths = _grid(_document(tmp_path, '\n[table]\ncol_widths = ["3cm", "auto"]\n'))
    assert widths[0] == 1701  # 3cm
    assert widths[1] > widths[0]


def test_auto_width_total_matches_content_width(tmp_path: Path) -> None:
    document = _document(tmp_path, '\n[table]\ncol_widths = "auto"\n')
    total = sum(_grid(document))
    tbl = re.search(r'<w:tblW [^>]*w:w="(\d+)"', document)
    assert tbl is not None
    assert total == int(tbl.group(1))


def test_mixed_number_and_auto_raises(tmp_path: Path) -> None:
    with pytest.raises(DocGenError) as caught:
        _document(tmp_path, '\n[table]\ncol_widths = [1, "auto"]\n')
    assert caught.value.code == "E5001"


def test_row_height_marker_only_affects_that_row(tmp_path: Path) -> None:
    markdown = """| A | B |
| --- | --- |
| [[row-height:1.2cm]] 1 | 2 |
| 3 | 4 |
"""
    document = _document(tmp_path, markdown=markdown)
    heights = re.findall(r'<w:trHeight w:val="(\d+)" w:hRule="([^"]+)"/>', document)
    assert heights == [("680", "atLeast")]
    assert "row-height" not in document

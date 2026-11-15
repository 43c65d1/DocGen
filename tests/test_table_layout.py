"""表格布局：行高、按厘米列宽、单元格垂直居中。"""

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

BASE = 'config_version = "0.1"\n\n[table]\nstyle = "grid"\n'
TABLE = "| 项目 | 说明 |\n| --- | --- |\n| A | 第一行 |\n| B | 第二行 |\n"


def _config(tmp_path: Path, extra: str = "") -> Config:
    path = tmp_path / "c.toml"
    path.write_text(BASE + extra, encoding="utf-8")
    return load_config(path)


def _document(tmp_path: Path, extra: str = "", markdown: str = TABLE) -> str:
    data = render_docx_bytes(parse_dfm(markdown), _config(tmp_path, extra), base_dir=tmp_path)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return archive.read("word/document.xml").decode("utf-8")


def test_row_height_and_header_override(tmp_path: Path) -> None:
    document = _document(
        tmp_path,
        '\nrow_height = "0.8cm"\nheader_row_height = "1cm"\nrow_height_rule = "atLeast"\n',
    )
    heights = re.findall(r"<w:trHeight [^>]*/>", document)
    assert heights == [
        '<w:trHeight w:val="567" w:hRule="atLeast"/>',  # 1cm
        '<w:trHeight w:val="454" w:hRule="atLeast"/>',  # 0.8cm
        '<w:trHeight w:val="454" w:hRule="atLeast"/>',
    ]


def test_row_height_exact_rule(tmp_path: Path) -> None:
    document = _document(tmp_path, '\nrow_height = "20pt"\nrow_height_rule = "exact"\n')
    assert all(
        'w:hRule="exact"' in item and 'w:val="400"' in item
        for item in re.findall(r"<w:trHeight [^>]*/>", document)
    )


def test_column_widths_in_cm(tmp_path: Path) -> None:
    document = _document(tmp_path, '\ncol_widths = ["3cm", "5cm"]\n')
    grid = re.findall(r"<w:gridCol w:w=\"(\d+)\"/>", document)
    assert [int(value) for value in grid] == [1701, 2835]  # 3cm / 5cm
    table_width = re.search(r"<w:tblW [^>]*/>", document)
    assert table_width is not None and 'w:w="4536"' in table_width.group(0)


def test_column_widths_mixed_units_rejected(tmp_path: Path) -> None:
    with pytest.raises(DocGenError) as caught:
        _document(tmp_path, '\ncol_widths = [3, "5cm"]\n')
    assert caught.value.code == "E5001"


def test_cell_vertical_alignment(tmp_path: Path) -> None:
    document = _document(tmp_path, '\ncell_vertical_align = "center"\n')
    values = re.findall(r"<w:vAlign w:val=\"([^\"]+)\"/>", document)
    assert values and all(value == "center" for value in values)


def test_default_no_row_height_or_valign(tmp_path: Path) -> None:
    document = _document(tmp_path)
    assert "<w:trHeight" not in document
    assert "<w:vAlign" not in document


@pytest.mark.parametrize(
    "extra",
    [
        '\nrow_height = "abc"\n',
        '\nrow_height_rule = "sometimes"\n',
        '\ncell_vertical_align = "middle"\n',
    ],
)
def test_invalid_layout_config(tmp_path: Path, extra: str) -> None:
    with pytest.raises(DocGenError) as caught:
        _document(tmp_path, extra)
    assert caught.value.code == "E5001"

"""逐单元格边框：``[[border:...]]``。"""

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
DOC = """| A | B |
| --- | --- |
| [[border:all style=double size=1.5pt color=FF0000]] 1 | 2 |
"""


def _config(tmp_path: Path, extra: str = "") -> Config:
    path = tmp_path / "c.toml"
    path.write_text(BASE + extra, encoding="utf-8")
    return load_config(path)


def _document(tmp_path: Path, markdown: str = DOC, extra: str = "") -> str:
    data = render_docx_bytes(parse_dfm(markdown), _config(tmp_path, extra), base_dir=tmp_path)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return archive.read("word/document.xml").decode("utf-8")


def _borders(document: str) -> list[str]:
    return re.findall(r"<w:tcBorders>.*?</w:tcBorders>", document, re.DOTALL)


def test_all_edges_style(tmp_path: Path) -> None:
    borders = _borders(_document(tmp_path))
    all_edges = [b for b in borders if 'w:val="double"' in b]
    assert all_edges
    block = all_edges[0]
    for edge in ("top", "left", "bottom", "right"):
        assert f"<w:{edge} " in block
    assert 'w:sz="12"' in block
    assert 'w:color="FF0000"' in block


def test_specific_edges_and_text_preserved(tmp_path: Path) -> None:
    markdown = """| A | B |
| --- | --- |
| 3 | [[border:top,bottom]] 4 |
"""
    document = _document(tmp_path, markdown)
    block = next(b for b in _borders(document) if 'w:val="single"' in b and "w:top" in b)
    assert "<w:left " not in block
    assert "<w:right " not in block
    assert "4" in document
    assert "border:" not in document


def test_merged_cell_border(tmp_path: Path) -> None:
    markdown = """| 项目 | [[border:all]] 说明 [[merge:2]] | |
| --- | --- | --- |
| A | B | C |
"""
    document = _document(tmp_path, markdown, '\n[table]\nstyle = "grid"\n')
    assert any(
        'w:color="auto"' in block or 'w:val="single"' in block for block in _borders(document)
    )
    assert "说明" in document


@pytest.mark.parametrize(
    ("marker", "code"),
    [
        ("[[border:tl2br]] x", "E5001"),
        ("[[border:all style=wavy]] x", "E5001"),
        ("[[border:all color=red]] x", "E5001"),
        ("[[border:all size=wide]] x", "E5001"),
        ("[[border:all space=abc]] x", "E5001"),
    ],
)
def test_invalid_marker_raises(tmp_path: Path, marker: str, code: str) -> None:
    markdown = f"| A | B |\n| --- | --- |\n| {marker} | 2 |\n"
    with pytest.raises(DocGenError) as caught:
        _document(tmp_path, markdown)
    assert caught.value.code == code

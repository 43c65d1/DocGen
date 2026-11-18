"""表格单元格内边距：``[table] cell_margin`` / ``cell_margin_*``。"""

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
DOC = "| A | B |\n| --- | --- |\n| 1 | 2 |\n"


def _config(tmp_path: Path, extra: str = "") -> Config:
    path = tmp_path / "c.toml"
    path.write_text(BASE + extra, encoding="utf-8")
    return load_config(path)


def _document(tmp_path: Path, extra: str = "") -> str:
    data = render_docx_bytes(parse_dfm(DOC), _config(tmp_path, extra), base_dir=tmp_path)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return archive.read("word/document.xml").decode("utf-8")


def _margins(document: str) -> dict[str, str]:
    match = re.search(r"<w:tblCellMar>.*?</w:tblCellMar>", document, re.DOTALL)
    assert match is not None
    return dict(
        re.findall(r'<w:(top|left|bottom|right) w:type="dxa" w:w="(\d+)"/>', match.group(0))
    )


def test_uniform_cell_margin(tmp_path: Path) -> None:
    margins = _margins(_document(tmp_path, '\n[table]\ncell_margin = "0.1cm"\n'))
    assert margins == {"top": "57", "left": "57", "bottom": "57", "right": "57"}


def test_edge_override(tmp_path: Path) -> None:
    margins = _margins(
        _document(
            tmp_path,
            '\n[table]\ncell_margin = "0.1cm"\ncell_margin_left = "0.2cm"\n',
        )
    )
    assert margins["left"] == "113"
    assert margins["right"] == "57"


def test_no_config_keeps_word_default(tmp_path: Path) -> None:
    assert "<w:tblCellMar>" not in _document(tmp_path)


@pytest.mark.parametrize("value", ["wide", "10furlong"])
def test_invalid_margin_raises(tmp_path: Path, value: str) -> None:
    with pytest.raises(DocGenError) as caught:
        _document(tmp_path, f'\n[table]\ncell_margin = "{value}"\n')
    assert caught.value.code == "E5001"

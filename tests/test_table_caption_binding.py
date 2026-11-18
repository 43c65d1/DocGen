"""表题与表格同页 / 表格行不跨页。"""

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
DOC = """\\begin{caption #tab:1 kind=table}
表题在上
\\end{caption}

| 表头A | 表头B |
| --- | --- |
| 1 | 2 |
| 3 | 4 |
"""


def _config(tmp_path: Path, extra: str = "") -> Config:
    path = tmp_path / "c.toml"
    path.write_text(BASE + extra, encoding="utf-8")
    return load_config(path)


def _document(tmp_path: Path, extra: str = "", markdown: str = DOC) -> str:
    data = render_docx_bytes(parse_dfm(markdown), _config(tmp_path, extra), base_dir=tmp_path)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return archive.read("word/document.xml").decode("utf-8")


def _caption_paragraph(document: str, needle: str = "表题在上") -> str:
    for paragraph in re.findall(r"<w:p(?: [^>]*)?>.*?</w:p>", document, re.DOTALL):
        if needle in paragraph:
            return str(paragraph)
    raise AssertionError("caption paragraph not found")


def test_table_caption_keeps_with_next_table(tmp_path: Path) -> None:
    paragraph = _caption_paragraph(_document(tmp_path))
    assert "<w:keepNext" in paragraph


def test_rows_cant_split_by_default(tmp_path: Path) -> None:
    document = _document(tmp_path)
    assert document.count("<w:cantSplit") == 3  # 表头 + 2 行数据


def test_rows_can_split_when_disabled(tmp_path: Path) -> None:
    document = _document(tmp_path, "\n[table]\nrows_keep_together = false\n")
    assert document.count("<w:cantSplit") == 1  # 只保留表头


def test_caption_after_table_does_not_keep_with_next(tmp_path: Path) -> None:
    markdown = """| 表头A | 表头B |
| --- | --- |
| 1 | 2 |

\\begin{caption #tab:1 kind=table}
表题在下
\\end{caption}
"""
    paragraph = _caption_paragraph(_document(tmp_path, markdown=markdown), "表题在下")
    assert "表题在下" in paragraph
    assert "<w:keepNext" not in paragraph


def test_invalid_rows_flag_raises(tmp_path: Path) -> None:
    with pytest.raises(DocGenError) as caught:
        _document(tmp_path, '\n[table]\nrows_keep_together = "maybe"\n')
    assert caught.value.code == "E5001"

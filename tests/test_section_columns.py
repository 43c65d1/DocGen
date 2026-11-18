"""分节栏数：``page.columns`` → ``w:cols``。"""

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


def _render(tmp_path: Path, sections: str, markdown: str = "# 标题\n\n正文。\n") -> str:
    config = tmp_path / "c.toml"
    config.write_text('config_version = "0.1"\n' + sections, encoding="utf-8")
    data = render_docx_bytes(parse_dfm(markdown), load_config(config), base_dir=tmp_path)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return archive.read("word/document.xml").decode("utf-8")


def _cols(document: str) -> list[dict[str, str]]:
    return [
        dict(re.findall(r'([\w:]+)="([^"]*)"', element))
        for element in re.findall(r"<w:cols [^>]*/>", document)
    ]


def test_single_column_shorthand(tmp_path: Path) -> None:
    cols = _cols(_render(tmp_path, "[[sections]]\npage.columns = 2\n"))
    assert cols[-1]["w:num"] == "2"
    assert cols[-1]["w:space"] == "357"  # 0.63cm


def test_column_table_space_separator(tmp_path: Path) -> None:
    sections = '[[sections]]\npage.columns = { count = 2, space = "0.5cm", separator = true }\n'
    cols = _cols(_render(tmp_path, sections))
    assert cols[-1]["w:num"] == "2"
    assert cols[-1]["w:space"] == "283"
    assert cols[-1]["w:sep"] == "1"


def test_sections_can_differ(tmp_path: Path) -> None:
    sections = "[[sections]]\npage.columns = 1\n\n[[sections]]\npage.columns = 2\n"
    markdown = "# 前置\n\n[[sectionbreak]]\n\n# 正文\n"
    cols = _cols(_render(tmp_path, sections, markdown))
    assert cols[0]["w:num"] == "1"
    assert cols[-1]["w:num"] == "2"


@pytest.mark.parametrize("value", ["0", "10", "abc"])
def test_invalid_count_raises(tmp_path: Path, value: str) -> None:
    with pytest.raises(DocGenError) as caught:
        _render(tmp_path, f"[[sections]]\npage.columns = {value!r}\n".replace("'", '"'))
    assert caught.value.code == "E5003"


def test_invalid_space_raises(tmp_path: Path) -> None:
    with pytest.raises(DocGenError) as caught:
        _render(
            tmp_path,
            '[[sections]]\npage.columns = { count = 2, space = "wide" }\n',
        )
    assert caught.value.code == "E5003"


def test_invalid_separator_raises(tmp_path: Path) -> None:
    with pytest.raises(DocGenError) as caught:
        _render(
            tmp_path,
            '[[sections]]\npage.columns = { count = 2, separator = "maybe" }\n',
        )
    assert caught.value.code == "E5003"

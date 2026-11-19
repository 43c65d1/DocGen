"""分节页面：B5 / 横向 / 装订线。"""

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


def _document(tmp_path: Path, sections: str) -> str:
    config = tmp_path / "c.toml"
    config.write_text('config_version = "0.1"\n' + sections, encoding="utf-8")
    data = render_docx_bytes(parse_dfm("# 标题\n\n正文\n"), load_config(config), base_dir=tmp_path)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return archive.read("word/document.xml").decode("utf-8")


def _pg_sz(document: str) -> dict[str, str]:
    match = re.search(r"<w:pgSz [^>]*/>", document)
    assert match is not None
    return dict(re.findall(r'([\w:]+)="([^"]*)"', match.group(0)))


def test_b5_portrait(tmp_path: Path) -> None:
    pg_sz = _pg_sz(_document(tmp_path, '[[sections]]\npage.size = "B5"\n'))
    assert pg_sz["w:w"] == "9978"
    assert pg_sz["w:h"] == "14173"
    assert "w:orient" not in pg_sz


def test_b5_landscape_swaps_dimensions(tmp_path: Path) -> None:
    pg_sz = _pg_sz(
        _document(
            tmp_path,
            '[[sections]]\npage.size = "B5"\npage.orientation = "landscape"\n',
        )
    )
    assert pg_sz["w:w"] == "14173"
    assert pg_sz["w:h"] == "9978"
    assert pg_sz["w:orient"] == "landscape"


def test_custom_dimensions_not_swapped(tmp_path: Path) -> None:
    pg_sz = _pg_sz(
        _document(
            tmp_path,
            '[[sections]]\npage.width = 20\npage.height = 30\npage.orientation = "landscape"\n',
        )
    )
    assert pg_sz["w:w"] == "11339"  # 20cm
    assert pg_sz["w:h"] == "17008"  # 30cm
    assert pg_sz["w:orient"] == "landscape"


def test_gutter(tmp_path: Path) -> None:
    document = _document(tmp_path, "[[sections]]\npage.gutter = 0.5\n")
    match = re.search(r"<w:pgMar [^>]*/>", document)
    assert match is not None
    assert 'w:gutter="283"' in match.group(0)


@pytest.mark.parametrize("value", ["diagonal", "true"])
def test_invalid_orientation_raises(tmp_path: Path, value: str) -> None:
    with pytest.raises(DocGenError) as caught:
        _document(tmp_path, f"[[sections]]\npage.orientation = {value!r}\n".replace("'", '"'))
    assert caught.value.code == "E5003"


def test_invalid_gutter_raises(tmp_path: Path) -> None:
    with pytest.raises(DocGenError) as caught:
        _document(tmp_path, '[[sections]]\npage.gutter = "wide"\n')
    assert caught.value.code == "E5003"

"""超链接样式：``[styles.hyperlink]`` 颜色/下划线。"""

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
DOC = "看[链接](https://example.com)。\n"


def _config(tmp_path: Path, extra: str = "") -> Config:
    path = tmp_path / "c.toml"
    path.write_text(BASE + extra, encoding="utf-8")
    return load_config(path)


def _hyperlink(tmp_path: Path, extra: str = "") -> str:
    data = render_docx_bytes(parse_dfm(DOC), _config(tmp_path, extra), base_dir=tmp_path)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        document = archive.read("word/document.xml").decode("utf-8")
    match = re.search(r"<w:hyperlink.*?</w:hyperlink>", document, re.DOTALL)
    assert match is not None
    return match.group(0)


def test_default_link_blue_with_underline(tmp_path: Path) -> None:
    hyperlink = _hyperlink(tmp_path)
    assert '<w:color w:val="0563C1"/>' in hyperlink
    assert '<w:u w:val="single"/>' in hyperlink


def test_custom_link_color(tmp_path: Path) -> None:
    hyperlink = _hyperlink(tmp_path, '\n[styles.hyperlink]\nfont.color = "000000"\n')
    assert '<w:color w:val="000000"/>' in hyperlink
    assert '<w:u w:val="single"/>' in hyperlink


def test_link_without_underline(tmp_path: Path) -> None:
    hyperlink = _hyperlink(
        tmp_path,
        '\n[styles.hyperlink]\nfont.color = "000000"\nunderline = "none"\n',
    )
    assert '<w:color w:val="000000"/>' in hyperlink
    assert "<w:u " not in hyperlink


def test_link_color_auto_removes_direct_color(tmp_path: Path) -> None:
    hyperlink = _hyperlink(tmp_path, '\n[styles.hyperlink]\nfont.color = "auto"\n')
    assert "<w:color " not in hyperlink
    assert '<w:u w:val="single"/>' in hyperlink


@pytest.mark.parametrize("value", ["red", "12345", "#GGGGGG"])
def test_invalid_link_color_raises(tmp_path: Path, value: str) -> None:
    extra = f'\n[styles.hyperlink]\nfont.color = "{value}"\n'
    with pytest.raises(DocGenError) as caught:
        _hyperlink(tmp_path, extra)
    assert caught.value.code == "E5001"


def test_invalid_link_underline_raises(tmp_path: Path) -> None:
    with pytest.raises(DocGenError) as caught:
        _hyperlink(tmp_path, '\n[styles.hyperlink]\nunderline = "dotted"\n')
    assert caught.value.code == "E5001"

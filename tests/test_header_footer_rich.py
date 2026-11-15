"""页眉页脚：奇偶页不同、粗细双线、字体、距边界、首页不同。"""

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

BASE = 'config_version = "0.1"\n\n[[sections]]\npage.size = "A4"\n'
DOC = "# 题目\n\n第一页。\n\n[[pagebreak]]\n\n第二页。\n"


def _config(tmp_path: Path, extra: str = "") -> Config:
    path = tmp_path / "c.toml"
    path.write_text(BASE + extra, encoding="utf-8")
    return load_config(path)


def _render(tmp_path: Path, extra: str = "", markdown: str = DOC) -> zipfile.ZipFile:
    data = render_docx_bytes(parse_dfm(markdown), _config(tmp_path, extra), base_dir=tmp_path)
    return zipfile.ZipFile(io.BytesIO(data))


def _part_texts(archive: zipfile.ZipFile, pattern: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for name in archive.namelist():
        if re.fullmatch(pattern, name):
            xml = archive.read(name).decode("utf-8")
            result[name] = "".join(re.findall(r"<w:t(?: [^>]*)?>(.*?)</w:t>", xml, re.DOTALL))
    return result


def _header_part(archive: zipfile.ZipFile, name: str) -> str:
    return archive.read(name).decode("utf-8")


# --------------------------------------------------------------------------
# 奇偶页不同
# --------------------------------------------------------------------------
def test_even_odd_headers(tmp_path: Path) -> None:
    archive = _render(
        tmp_path,
        """
header.odd.text = "奇数页页眉"
header.even.text = "偶数页页眉"
""",
    )
    settings = archive.read("word/settings.xml").decode("utf-8")
    assert "evenAndOddHeaders" in settings
    document = archive.read("word/document.xml").decode("utf-8")
    assert 'w:type="default"' in document
    assert 'w:type="even"' in document
    headers = _part_texts(archive, r"word/header\d*\.xml")
    assert sorted(headers.values()) == ["偶数页页眉", "奇数页页眉"]


def test_no_even_setting_without_even_config(tmp_path: Path) -> None:
    archive = _render(tmp_path, '\nheader.text = "普通页眉"\n')
    settings = archive.read("word/settings.xml").decode("utf-8")
    assert "evenAndOddHeaders" not in settings
    headers = _part_texts(archive, r"word/header\d*\.xml")
    assert list(headers.values()) == ["普通页眉"]


# --------------------------------------------------------------------------
# 线 / 字体 / 距边界
# --------------------------------------------------------------------------
def test_header_double_line_and_font(tmp_path: Path) -> None:
    archive = _render(
        tmp_path,
        """
header.text = "页眉"
header.line = "double"
header.line_size = "1.5pt"
header.line_color = "000000"
header.font.name = "宋体"
header.font.size = "小五"
""",
    )
    headers = _part_texts(archive, r"word/header\d*\.xml")
    xml = _header_part(archive, next(iter(headers)))
    assert 'w:val="thickThinSmallGap"' in xml  # double → 粗上细下
    assert 'w:sz="12"' in xml  # 1.5pt = 12 eighths
    assert 'w:sz w:val="18"' in xml  # 9pt 字体
    assert 'w:eastAsia="宋体"' in xml


def test_header_footer_distances(tmp_path: Path) -> None:
    archive = _render(
        tmp_path,
        """
header.text = "页眉"
header.distance = 1.5
footer.text = "第 PAGE 页"
footer.distance = 1.0
""",
    )
    document = archive.read("word/document.xml").decode("utf-8")
    margin = re.search(r"<w:pgMar [^>]*/>", document)
    assert margin is not None
    # 1.5cm = 850 twips；1.0cm = 567 twips
    assert 'w:header="850"' in margin.group(0)
    assert 'w:footer="567"' in margin.group(0)


def test_footer_page_field_and_font(tmp_path: Path) -> None:
    archive = _render(
        tmp_path,
        """
footer.text = "第 PAGE 页"
footer.font.size = "小五"
""",
    )
    footers = _part_texts(archive, r"word/footer\d*\.xml")
    assert list(footers.values()) == ["第 1 页"]
    footer_xml = _header_part(archive, next(iter(footers)))
    assert "PAGE" in footer_xml
    assert 'w:sz w:val="18"' in footer_xml


# --------------------------------------------------------------------------
# 首页不同
# --------------------------------------------------------------------------
def test_first_page_header(tmp_path: Path) -> None:
    archive = _render(
        tmp_path,
        """
header.text = "普通页眉"
header.first.text = "首页页眉"
""",
    )
    document = archive.read("word/document.xml").decode("utf-8")
    assert "titlePg" in document
    headers = _part_texts(archive, r"word/header\d*\.xml")
    assert set(headers.values()) == {"普通页眉", "首页页眉"}


# --------------------------------------------------------------------------
# 校验
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "extra",
    [
        '\nheader.text = "x"\nheader.alignment = "justify"\n',
        '\nheader.text = "x"\nheader.line = "wavy"\n',
        '\nheader.text = "x"\nheader.distance = "abc"\n',
    ],
)
def test_invalid_header_config(tmp_path: Path, extra: str) -> None:
    with pytest.raises(DocGenError) as caught:
        _render(tmp_path, extra)
    assert caught.value.code == "E5003"

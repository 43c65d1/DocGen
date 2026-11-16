"""插图清单 / 附表清单：题注编号 + PAGEREF 页码域。"""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

import pytest

from docgen.config import Config, load_config
from docgen.errors import DocGenError
from docgen.ir import CaptionList
from docgen.parser.dfm import parse_dfm
from docgen.render.docx import render_docx_bytes

BASE = 'config_version = "0.1"\n\n[list]\nfigures = "插图清单"\ntables = "附表清单"\n'
DOC = """\
# 第一章

[[list:figures]]

[[list:tables]]

正文。

\\begin{caption #fig:1}
图一说明
\\end{caption}

\\begin{table #tab:1}
表一说明
\\end{table}

[[pagebreak]]

\\begin{caption #fig:2}
图二说明
\\end{caption}
"""


def _config(tmp_path: Path, extra: str = "") -> Config:
    path = tmp_path / "c.toml"
    path.write_text(BASE + extra, encoding="utf-8")
    return load_config(path)


def _document(tmp_path: Path, extra: str = "", markdown: str = DOC) -> str:
    data = render_docx_bytes(parse_dfm(markdown), _config(tmp_path, extra), base_dir=tmp_path)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return archive.read("word/document.xml").decode("utf-8")


def _texts(document: str) -> list[str]:
    paragraphs = re.findall(r"<w:p(?: [^>]*)?>.*?</w:p>", document, re.DOTALL)
    return [
        "".join(re.findall(r"<w:t(?: [^>]*)?>(.*?)</w:t>", paragraph, re.DOTALL))
        for paragraph in paragraphs
    ]


# --------------------------------------------------------------------------
# 解析
# --------------------------------------------------------------------------
def test_parse_markers() -> None:
    blocks = parse_dfm("[[list:figures]]\n\n[[list:tables]]\n")
    assert isinstance(blocks[0], CaptionList) and blocks[0].kind == "figures"
    assert isinstance(blocks[1], CaptionList) and blocks[1].kind == "tables"


# --------------------------------------------------------------------------
# 渲染
# --------------------------------------------------------------------------
def test_figure_list_entries(tmp_path: Path) -> None:
    document = _document(tmp_path)
    texts = _texts(document)
    assert "插图清单" in texts
    assert "图 1 图一说明" in texts
    assert "图 2 图二说明" in texts
    assert "PAGEREF fig:1 \\h" in document
    assert "PAGEREF fig:2 \\h" in document


def test_table_list_entries(tmp_path: Path) -> None:
    document = _document(tmp_path)
    texts = _texts(document)
    assert "附表清单" in texts
    assert "表 1 表一说明" in texts
    assert "PAGEREF tab:1 \\h" in document
    assert "PAGEREF fig:1 \\h" not in document.split("附表清单", 1)[1]


def test_dot_leader_tab(tmp_path: Path) -> None:
    document = _document(tmp_path)
    assert 'w:leader="dot"' in document
    assert 'w:val="right"' in document


def test_chapter_numbering_in_list(tmp_path: Path) -> None:
    document = _document(
        tmp_path,
        extra='\n[document]\ncaption_numbering = "chapter"\n',
        markdown="# 第一章\n\n[[list:figures]]\n\n"
        "\\begin{caption #fig:1}\n图一\n\\end{caption}\n\n"
        "# 第二章\n\n\\begin{caption #fig:2}\n图二\n\\end{caption}\n",
    )
    texts = _texts(document)
    assert "图 1-1 图一" in texts
    assert "图 2-1 图二" in texts


def test_title_config_and_heading_level(tmp_path: Path) -> None:
    document = _document(
        tmp_path,
        extra="\nheading_level = 2\n",
        markdown="[[list:figures]]\n",
    )
    assert "插图清单" in _texts(document)
    # 二级标题样式
    assert 'w:pStyle w:val="Heading2"' in document


def test_empty_list_still_has_title(tmp_path: Path) -> None:
    texts = _texts(_document(tmp_path, markdown="[[list:figures]]\n"))
    assert texts == ["插图清单"]


def test_chapter_numbering_preset_combined(tmp_path: Path) -> None:
    document = _document(
        tmp_path,
        extra='\n[document]\nheading_numbering = "chapter"\ncaption_numbering = "chapter"\n',
        markdown="# 绪论\n\n[[list:figures]]\n\n\\begin{caption #fig:1}\n图一\n\\end{caption}\n",
    )
    texts = _texts(document)
    assert "第一章 绪论" in texts
    assert "图 1-1 图一" in texts


# --------------------------------------------------------------------------
# 校验
# --------------------------------------------------------------------------
@pytest.mark.parametrize("level", ["0", "10", "abc"])
def test_invalid_heading_level(tmp_path: Path, level: str) -> None:
    with pytest.raises(DocGenError) as caught:
        _document(
            tmp_path,
            extra=f"\nheading_level = {level!r}\n".replace("'", '"'),
            markdown="[[list:figures]]\n",
        )
    assert caught.value.code == "E5001"

"""公式自动编号：``[math] numbering = "auto" / "chapter"``。"""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

import pytest

from docgen.config import Config, load_config
from docgen.errors import DocGenError
from docgen.numbering import equation_numbering_mode, equation_numbers
from docgen.parser.dfm import parse_dfm
from docgen.render.docx import render_docx_bytes
from docgen.validate import validate_content

BASE = 'config_version = "0.1"\n'
DOC = """\
引用[[ref:eq:a]]。

\\begin{equation #eq:a}
$$x=1$$
\\end{equation}

\\begin{equation}
$$y=2$$
\\end{equation}

\\begin{equation #eq:b}
$$z=3$$
\\end{equation}
"""
CHAPTER = """\
# 第一章

\\begin{equation #eq:a}
$$x=1$$
\\end{equation}

# 第二章

\\begin{equation #eq:b}
$$y=2$$
\\end{equation}
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
    return [t for t in re.findall(r"<w:t(?: [^>]*)?>(.*?)</w:t>", document, re.DOTALL) if t.strip()]


def _numbers(document: str) -> list[str]:
    """文档里所有 ``(N)`` / ``(2-1)``（公式编号 + REF 缓存值）。"""
    return re.findall(r"\(\d+(?:-\d+)?\)", document)


@pytest.mark.parametrize(
    ("snippet", "mode"),
    [
        ('[math]\nnumbering = "none"\n', "none"),
        ('[math]\nnumbering = "auto"\n', "auto"),
        ('[math]\nnumbering = "chapter"\n', "chapter"),
        ("[math]\nnumbering = false\n", "none"),
        ("[math]\nnumbering = true\n", "auto"),
    ],
)
def test_mode_parsing(tmp_path: Path, snippet: str, mode: str) -> None:
    assert equation_numbering_mode(_config(tmp_path, "\n" + snippet)) == mode


def test_invalid_mode_raises(tmp_path: Path) -> None:
    with pytest.raises(DocGenError) as caught:
        equation_numbering_mode(_config(tmp_path, '\n[math]\nnumbering = "roman"\n'))
    assert caught.value.code == "E5001"


def test_invalid_mode_reported_by_validate(tmp_path: Path) -> None:
    errors = validate_content(
        parse_dfm("\\begin{equation}\n$$x$$\n\\end{equation}\n"),
        _config(tmp_path, '\n[math]\nnumbering = "roman"\n'),
    )
    assert any(error.code == "E5001" for error in errors)


def test_auto_numbering(tmp_path: Path) -> None:
    document = _document(tmp_path, '\n[math]\nnumbering = "auto"\n')
    assert _numbers(document) == ["(1)", "(1)", "(2)", "(3)"]


def test_auto_numbering_bookmarks_only_labeled(tmp_path: Path) -> None:
    document = _document(tmp_path, '\n[math]\nnumbering = "auto"\n')
    assert 'w:name="eq:a"' in document
    assert 'w:name="eq:b"' in document
    assert document.count('w:name="eq:') == 2


def test_chapter_numbering(tmp_path: Path) -> None:
    document = _document(tmp_path, '\n[math]\nnumbering = "chapter"\n', markdown=CHAPTER)
    assert _numbers(document) == ["(1-1)", "(2-1)"]


def test_manual_number_wins_and_syncs_counter(tmp_path: Path) -> None:
    markdown = """\\begin{equation #eq:a number=7}
$$x$$
\\end{equation}

\\begin{equation #eq:b}
$$y$$
\\end{equation}
"""
    document = _document(tmp_path, '\n[math]\nnumbering = "auto"\n', markdown=markdown)
    assert _numbers(document) == ["(7)", "(8)"]


def test_default_none_keeps_formula_without_number_plain(tmp_path: Path) -> None:
    document = _document(tmp_path)
    assert "<w:tbl>" not in document
    assert _numbers(document) == []


def test_manual_number_without_auto_mode(tmp_path: Path) -> None:
    markdown = "\\begin{equation #eq:a number=5}\n$$x$$\n\\end{equation}\n"
    assert _numbers(_document(tmp_path, markdown=markdown)) == ["(5)"]


def test_equation_numbers_map(tmp_path: Path) -> None:
    blocks = parse_dfm(DOC)
    numbers = equation_numbers(blocks, _config(tmp_path, '\n[math]\nnumbering = "auto"\n'))
    assert sorted(numbers.values()) == ["1", "2", "3"]

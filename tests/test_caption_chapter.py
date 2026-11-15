"""图/表按章编号（图 2-1）：与一级标题联动。"""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

import pytest

from docgen.config import Config, load_config
from docgen.errors import DocGenError
from docgen.numbering import caption_numbering_mode, caption_numbers
from docgen.parser.dfm import parse_dfm
from docgen.render.docx import render_docx_bytes
from docgen.validate import validate_content

BASE = 'config_version = "0.1"\n\n[document]\nfont.name = "宋体"\n'
DOC = """\
# 绪论

正文见[[ref:fig:1]]。

\\begin{caption #fig:1}
图一
\\end{caption}

\\begin{table #tab:1}
表一
\\end{table}

## 小节

\\begin{caption #fig:2}
图二
\\end{caption}

# 方法

\\begin{caption #fig:3}
图三
\\end{caption}

\\begin{table #tab:2}
表二
\\end{table}
"""


def _config(tmp_path: Path, extra: str = "") -> Config:
    path = tmp_path / "c.toml"
    path.write_text(BASE + extra, encoding="utf-8")
    return load_config(path)


def _render(tmp_path: Path, markdown: str = DOC, extra: str = "") -> str:
    data = render_docx_bytes(parse_dfm(markdown), _config(tmp_path, extra), base_dir=tmp_path)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return archive.read("word/document.xml").decode("utf-8")


def _paragraph_texts(document: str) -> list[str]:
    paragraphs = re.findall(r"<w:p(?: [^>]*)?>.*?</w:p>", document, re.DOTALL)
    texts = []
    for paragraph in paragraphs:
        text = "".join(re.findall(r"<w:t(?: [^>]*)?>(.*?)</w:t>", paragraph, re.DOTALL))
        if text.strip():
            texts.append(text)
    return texts


# --------------------------------------------------------------------------
# 模式与编号
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("snippet", "mode"),
    [
        ("caption_numbering = false", "continuous"),
        ("caption_numbering = true", "chapter"),
        ('caption_numbering = "continuous"', "continuous"),
        ('caption_numbering = "chapter"', "chapter"),
        ('caption_numbering = "by-chapter"', "chapter"),
        ('caption_numbering = "CHAPTER"', "chapter"),
    ],
)
def test_mode_parsing(tmp_path: Path, snippet: str, mode: str) -> None:
    assert caption_numbering_mode(_config(tmp_path, "\n" + snippet + "\n")) == mode


def test_invalid_mode_raises(tmp_path: Path) -> None:
    with pytest.raises(DocGenError) as caught:
        caption_numbering_mode(_config(tmp_path, '\ncaption_numbering = "section"\n'))
    assert caught.value.code == "E5001"


def test_invalid_mode_reported_by_validate(tmp_path: Path) -> None:
    errors = validate_content(
        parse_dfm("# 标题\n"),
        _config(tmp_path, '\ncaption_numbering = "section"\n'),
    )
    assert any(error.code == "E5001" for error in errors)


def test_caption_numbers_continuous(tmp_path: Path) -> None:
    numbers = caption_numbers(parse_dfm(DOC), _config(tmp_path))
    assert numbers == {"fig:1": "1", "tab:1": "1", "fig:2": "2", "fig:3": "3", "tab:2": "2"}


def test_caption_numbers_by_chapter(tmp_path: Path) -> None:
    numbers = caption_numbers(
        parse_dfm(DOC), _config(tmp_path, '\ncaption_numbering = "chapter"\n')
    )
    assert numbers == {
        "fig:1": "1-1",
        "tab:1": "1-1",
        "fig:2": "1-2",
        "fig:3": "2-1",
        "tab:2": "2-1",
    }


def test_caption_before_first_chapter_has_no_chapter_prefix(tmp_path: Path) -> None:
    markdown = "\\begin{caption #fig:0}\n图零\n\\end{caption}\n\n# 第一章\n"
    numbers = caption_numbers(
        parse_dfm(markdown), _config(tmp_path, '\ncaption_numbering = "chapter"\n')
    )
    assert numbers == {"fig:0": "1"}


# --------------------------------------------------------------------------
# 渲染
# --------------------------------------------------------------------------
def test_render_chapter_captions(tmp_path: Path) -> None:
    document = _render(tmp_path, extra='\ncaption_numbering = "chapter"\n')
    texts = _paragraph_texts(document)
    assert "图 1-1 图一" in texts
    assert "表 1-1 表一" in texts
    assert "图 1-2 图二" in texts
    assert "图 2-1 图三" in texts
    assert "表 2-1 表二" in texts
    assert "正文见1-1。" in texts


def test_chapter_captions_use_static_text_not_seq_fields(tmp_path: Path) -> None:
    document = _render(tmp_path, extra='\ncaption_numbering = "chapter"\n')
    assert "SEQ 图" not in document
    assert "SEQ 表" not in document
    # 书签仍包住编号，供 REF 使用
    assert 'w:name="fig:1"' in document
    assert 'w:name="tab:1"' in document


def test_default_captions_still_use_seq_fields(tmp_path: Path) -> None:
    document = _render(tmp_path)
    assert "SEQ 图" in document
    texts = _paragraph_texts(document)
    assert "图 1 图一" in texts


def test_chapter_caption_with_chapter_heading_preset(tmp_path: Path) -> None:
    document = _render(
        tmp_path,
        extra='\nheading_numbering = "chapter"\ncaption_numbering = "chapter"\n',
    )
    texts = _paragraph_texts(document)
    assert "第一章 绪论" in texts
    assert "图 1-1 图一" in texts
    assert "第二章 方法" in texts
    assert "图 2-1 图三" in texts


def test_equation_numbering_not_affected(tmp_path: Path) -> None:
    markdown = "# 第一章\n\n\\begin{equation #eq:1 number=1}\n$$x=1$$\n\\end{equation}\n"
    document = _render(tmp_path, markdown=markdown, extra='\ncaption_numbering = "chapter"\n')
    texts = _paragraph_texts(document)
    assert "(1)" in texts

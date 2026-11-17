"""子图：``\\begin{subfigures}`` + ``\\begin{subfigure}``。"""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

from docgen.config import Config, load_config
from docgen.ir import NamedBlock
from docgen.parser.dfm import parse_dfm
from docgen.render.docx import render_docx_bytes

FIXTURES = Path(__file__).parent / "fixtures"
BASE = 'config_version = "0.1"\n'
DOC = """\
见[[ref:fig:a]]与[[ref:fig:b]]。

\\begin{subfigures}
\\begin{subfigure #fig:a}
[[img:pics/photo.png width=3cm]]

左图说明
\\end{subfigure}
\\begin{subfigure #fig:b}
[[img:pics/photo.png width=3cm]]

右图说明
\\end{subfigure}
\\end{subfigures}

\\begin{caption #fig:1}
总图题
\\end{caption}
"""


def _config(tmp_path: Path, extra: str = "") -> Config:
    path = tmp_path / "c.toml"
    path.write_text(BASE + extra, encoding="utf-8")
    return load_config(path)


def _document(tmp_path: Path, extra: str = "", markdown: str = DOC) -> str:
    data = render_docx_bytes(parse_dfm(markdown), _config(tmp_path, extra), base_dir=FIXTURES)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return archive.read("word/document.xml").decode("utf-8")


def _texts(document: str) -> list[str]:
    return [t for t in re.findall(r"<w:t(?: [^>]*)?>(.*?)</w:t>", document, re.DOTALL) if t.strip()]


def test_parse_nested_labels() -> None:
    blocks = parse_dfm(DOC)
    container = blocks[1]
    assert isinstance(container, NamedBlock)
    assert container.name == "subfigures"
    children = [child for child in container.content if isinstance(child, NamedBlock)]
    assert [child.label for child in children] == ["fig:a", "fig:b"]


def test_render_subfigures_table_and_refs(tmp_path: Path) -> None:
    document = _document(tmp_path)
    texts = _texts(document)
    assert "（a）左图说明" in texts
    assert "（b）右图说明" in texts
    assert "总图题" in "".join(texts)
    assert "1（a）" in texts
    assert "1（b）" in texts
    assert "REF fig:a" not in document  # 子图引用是静态烘焙，不是 REF 域
    assert document.count("<w:drawing") == 2
    assert 'w:name="fig:a"' in document
    assert 'w:name="fig:b"' in document
    assert 'w:name="fig:1"' in document


def test_chapter_numbering_subfigure_refs(tmp_path: Path) -> None:
    markdown = "# 第一章\n\n" + DOC
    document = _document(
        tmp_path, '\n[document]\ncaption_numbering = "chapter"\n', markdown=markdown
    )
    texts = _texts(document)
    assert "1-1（a）" in texts
    assert "1-1（b）" in texts


def test_image_without_width_has_no_em_dash_paragraph(tmp_path: Path) -> None:
    document = _document(tmp_path, markdown="[[img:pics/photo.png]]\n")
    assert "\u2014" not in document
    assert "—" * 20 not in document


def test_inline_image_and_subcaption_one_paragraph(tmp_path: Path) -> None:
    markdown = """\\begin{subfigures}
\\begin{subfigure #fig:a}
![左](pics/photo.png)
左说明
\\end{subfigure}
\\begin{subfigure #fig:b}
![右](pics/photo.png)
右说明
\\end{subfigure}
\\end{subfigures}

\\begin{caption #fig:1}
总图题
\\end{caption}
"""
    document = _document(tmp_path, markdown=markdown)
    texts = _texts(document)
    assert "（a）左说明" in texts
    assert "（b）右说明" in texts
    assert document.count("<w:drawing") == 2

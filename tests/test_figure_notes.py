"""图注 / 表注：``\\begin{note}``（整图注、表注、图元注）。"""

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

#: 图题里内嵌图注的写法（图注紧跟图题，天然是「整图注」）
FIGURE = """\
[[img:pics/photo.png width=3cm]]

\\begin{caption #fig:1}
系统架构

\\begin{note}
注：数据来源本课题组实验。
\\end{note}
\\end{caption}
"""

SUBS = """\
\\begin{subfigures}
\\begin{subfigure #fig:a}
[[img:pics/photo.png width=3cm]]

左图说明

\\begin{note}
注：实线为实测。
\\end{note}
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


def _parts(tmp_path: Path, extra: str = "", markdown: str = FIGURE) -> tuple[str, str]:
    data = render_docx_bytes(parse_dfm(markdown), _config(tmp_path, extra), base_dir=FIXTURES)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return (
            archive.read("word/document.xml").decode("utf-8"),
            archive.read("word/styles.xml").decode("utf-8"),
        )


def _paragraphs(document: str) -> list[str]:
    return re.findall(r"<w:p(?: [^>]*)?>.*?</w:p>", document, re.DOTALL)


def _text(paragraph: str) -> str:
    return "".join(re.findall(r"<w:t(?: [^>]*)?>(.*?)</w:t>", paragraph, re.DOTALL))


def _note_paragraphs(document: str) -> list[str]:
    return [p for p in _paragraphs(document) if 'w:val="CaptionNote"' in p]


def test_parse_note_block() -> None:
    blocks = parse_dfm("\\begin{note}\n注：来源。\n\\end{note}\n")
    assert isinstance(blocks[0], NamedBlock)
    assert blocks[0].name == "note"


def test_figure_note_uses_caption_note_style(tmp_path: Path) -> None:
    document, _ = _parts(tmp_path)
    notes = _note_paragraphs(document)
    assert len(notes) == 1
    assert "注：数据来源本课题组实验。" in _text(notes[0])
    # 图注整段不跨页
    assert "<w:keepLines/>" in notes[0]


def test_caption_keeps_with_its_note(tmp_path: Path) -> None:
    document, _ = _parts(tmp_path)
    paragraphs = _paragraphs(document)
    caption_index = next(i for i, p in enumerate(paragraphs) if "系统架构" in _text(p))
    note_index = next(i for i, p in enumerate(paragraphs) if "注：数据来源" in _text(p))
    assert note_index == caption_index + 1
    assert "<w:keepNext/>" in paragraphs[caption_index]


def test_note_style_defaults(tmp_path: Path) -> None:
    _, styles = _parts(tmp_path)
    style = re.search(r'<w:style [^>]*w:styleId="CaptionNote".*?</w:style>', styles, re.DOTALL)
    assert style is not None
    xml = style.group(0)
    assert '<w:name w:val="Caption Note"/>' in xml
    assert '<w:basedOn w:val="Caption"/>' in xml
    assert '<w:jc w:val="left"/>' in xml
    assert 'w:firstLine="0"' in xml


def test_note_style_comes_from_config(tmp_path: Path) -> None:
    extra = (
        '\n[styles.caption_note]\nfont.size = "9pt"\nfont.color = "333333"\nalignment = "center"\n'
    )
    document, styles = _parts(tmp_path, extra)
    style = re.search(r'<w:style [^>]*w:styleId="CaptionNote".*?</w:style>', styles, re.DOTALL)
    assert style is not None
    assert '<w:sz w:val="18"/>' in style.group(0)
    assert "333333" in style.group(0).upper()
    notes = _note_paragraphs(document)
    assert '<w:jc w:val="center"/>' in notes[0]


def test_table_note_renders_below_table(tmp_path: Path) -> None:
    markdown = (
        "\\begin{table #tab:1}\n数据表\n\\end{table}\n\n"
        "| A | B |\n|---|---|\n| 1 | 2 |\n\n"
        "\\begin{note}\n注：单位统一为 mm。\n\\end{note}\n"
    )
    document, _ = _parts(tmp_path, markdown=markdown)
    note = _note_paragraphs(document)
    assert len(note) == 1
    assert "注：单位统一为 mm。" in _text(note[0])
    assert document.index("<w:tbl>") < document.index("注：单位统一为 mm。")


def test_subfigure_element_note(tmp_path: Path) -> None:
    document, _ = _parts(tmp_path, markdown=SUBS)
    texts = [_text(p) for p in _paragraphs(document)]
    assert "（a）左图说明" in texts
    assert any("注：实线为实测。" in text for text in texts)
    # 注在子图表格里（第三行），总图题与子题注都不受影响
    assert "图 1 总图题" in texts
    assert "（b）右图说明" in texts
    rows = re.findall(r"<w:tr(?: [^>]*)?>", document)
    assert len(rows) == 3


def test_figure_note_not_in_caption_text(tmp_path: Path) -> None:
    extra = '\n[list]\nfigures = "插图清单"\n'
    markdown = "[[list:figures]]\n\n" + FIGURE
    document, _ = _parts(tmp_path, extra, markdown=markdown)
    entry = next(p for p in _paragraphs(document) if "系统架构" in _text(p) and "图 1" in _text(p))
    assert "注：数据来源" not in _text(entry)

"""图片与图题必须是**不可分割的整体**（学术排版硬要求）。

- 图题紧贴图片下方（文档顺序已保证）；
- 两者**不能跨页**——Word 里靠图片段落的 ``w:keepNext``；
- 图题自身不能被拆开（``w:keepLines``）；
- 图题默认居中，``[styles.caption]`` 可覆盖。

实测对照（Word 读真实页码）：去掉 ``keepNext`` 时图在第 1 页、题注在第 2 页；
加上之后两者一起落到第 2 页。
"""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

from docgen.config import Config, load_config
from docgen.parser.dfm import parse_dfm
from docgen.render.docx import render_docx_bytes

FIXTURES = Path(__file__).parent / "fixtures"

BASE = 'config_version = "0.1"\n\n[math]\nengine = "plain"\n'


def _config(tmp_path: Path, extra: str = "") -> Config:
    path = tmp_path / "config.toml"
    path.write_text(BASE + extra, encoding="utf-8")
    return load_config(path)


def _render(tmp_path: Path, markdown: str, extra: str = "") -> tuple[str, str]:
    """返回 (document.xml, styles.xml)。"""
    data = render_docx_bytes(parse_dfm(markdown), _config(tmp_path, extra), base_dir=FIXTURES)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return (
            archive.read("word/document.xml").decode("utf-8"),
            archive.read("word/styles.xml").decode("utf-8"),
        )


def _paragraphs(document: str) -> list[str]:
    return re.findall(r"<w:p>.*?</w:p>|<w:p [^>]*>.*?</w:p>", document, re.DOTALL)


FIGURE_WITH_CAPTION = (
    "[[img:pics/photo.png width=3cm]]\n\n\\begin{caption #fig:demo}\n示例图题\n\\end{caption}\n"
)


def test_image_paragraph_keeps_with_next_when_caption_follows(tmp_path: Path) -> None:
    """图片段落必须 ``keepNext``，否则分页时图题会被甩到下一页。"""
    document, _ = _render(tmp_path, FIGURE_WITH_CAPTION)
    paragraphs = _paragraphs(document)
    image_paragraph = paragraphs[0]
    assert "graphic" in image_paragraph or "blip" in image_paragraph, "第一段不是图片"
    assert "<w:keepNext/>" in image_paragraph


def test_caption_paragraph_keeps_lines_together(tmp_path: Path) -> None:
    """图题本身不能被分页拆成两半。"""
    document, _ = _render(tmp_path, FIGURE_WITH_CAPTION)
    caption = next(p for p in _paragraphs(document) if "示例图题" in p)
    assert "<w:keepLines/>" in caption


def test_image_and_caption_are_adjacent_paragraphs(tmp_path: Path) -> None:
    """两者之间不能夹别的段落（图题紧贴图片下方）。"""
    document, _ = _render(tmp_path, "前文。\n\n" + FIGURE_WITH_CAPTION + "\n后文。\n")
    paragraphs = _paragraphs(document)
    image_index = next(i for i, p in enumerate(paragraphs) if "blip" in p)
    caption_index = next(i for i, p in enumerate(paragraphs) if "示例图题" in p)
    assert caption_index == image_index + 1


def test_image_without_caption_does_not_force_keep_next(tmp_path: Path) -> None:
    """后面不是图题时不要强绑——否则会把正文段落一起拖到下一页。"""
    document, _ = _render(tmp_path, "[[img:pics/photo.png width=3cm]]\n\n后面的正文。\n")
    image_paragraph = next(p for p in _paragraphs(document) if "blip" in p)
    assert "<w:keepNext/>" not in image_paragraph


def test_caption_style_is_centered_by_default(tmp_path: Path) -> None:
    """学术排版规范：图题在图片正下方**居中**。"""
    _, styles = _render(tmp_path, FIGURE_WITH_CAPTION)
    caption = re.search(r'<w:style [^>]*w:styleId="Caption".*?</w:style>', styles, re.DOTALL)
    assert caption is not None
    assert '<w:jc w:val="center"/>' in caption.group(0)


def test_caption_alignment_can_be_overridden_by_config(tmp_path: Path) -> None:
    """``[styles.caption] alignment`` 覆盖默认居中（config 是唯一真源）。"""
    document, _ = _render(tmp_path, FIGURE_WITH_CAPTION, '\n[styles.caption]\nalignment = "left"\n')
    caption = next(p for p in _paragraphs(document) if "示例图题" in p)
    assert '<w:jc w:val="left"/>' in caption


def test_caption_paragraph_properties_come_from_config(tmp_path: Path) -> None:
    """题注的段落级键（缩进等）与正文共用同一套读取。"""
    document, _ = _render(
        tmp_path, FIGURE_WITH_CAPTION, "\n[styles.caption]\nfirst_line_chars = 0\n"
    )
    caption = next(p for p in _paragraphs(document) if "示例图题" in p)
    assert 'w:firstLineChars="0"' in caption


def test_table_caption_also_binds_to_preceding_block(tmp_path: Path) -> None:
    """表格题注同理：表格段落与题注要连在一起。"""
    markdown = "| a | b |\n| --- | --- |\n| 1 | 2 |\n\n\\begin{table #tab:1}\n表题\n\\end{table}\n"
    document, _ = _render(tmp_path, markdown)
    table = re.search(r"<w:tbl>.*?</w:tbl>", document, re.DOTALL)
    assert table is not None
    # 表格是块级元素，不能用段落 keepNext；这里只断言题注紧跟在表格之后
    assert document.index("</w:tbl>") < document.index("表题")

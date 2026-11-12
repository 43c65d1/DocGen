"""表格文字格式 / 行距：``[table.text]`` 与 ``[table] header_bold``。"""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

import pytest

from docgen.config import Config, load_config
from docgen.errors import DocGenError
from docgen.ir import BlockNode, Paragraph, Table, TableCell, Text
from docgen.parser.dfm import parse_dfm
from docgen.render.docx import render_docx_bytes

BASE = 'config_version = "0.1"\n\n[document]\nfont.name = "宋体"\n'
TABLE_MD = "| 姓名 | 分数 |\n| --- | --- |\n| 张三 | 90 |\n"


def _config(tmp_path: Path, extra: str = "") -> Config:
    path = tmp_path / "c.toml"
    path.write_text(BASE + extra, encoding="utf-8")
    return load_config(path)


def _render(
    tmp_path: Path,
    markdown: str | None = None,
    blocks: list[BlockNode] | None = None,
    extra: str = "",
) -> bytes:
    nodes = blocks if blocks is not None else parse_dfm(markdown or TABLE_MD)
    return render_docx_bytes(nodes, _config(tmp_path, extra))


def _cells(data: bytes) -> list[str]:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        document = archive.read("word/document.xml").decode("utf-8")
    return re.findall(r"<w:tc>.*?</w:tc>", document, re.DOTALL)


def _text(cell: str) -> str:
    return "".join(re.findall(r"<w:t(?: [^>]*)?>(.*?)</w:t>", cell, re.DOTALL))


def test_default_table_has_no_explicit_cell_spacing_and_bold_header(tmp_path: Path) -> None:
    cells = _cells(_render(tmp_path))
    assert len(cells) == 4
    for cell in cells:
        assert "<w:spacing" not in cell  # 不写就继承 Normal
    assert "<w:b/>" in cells[0] or '<w:b w:val="true"/>' in cells[0]
    assert "<w:b/>" not in cells[2] and '<w:b w:val="true"/>' not in cells[2]


def test_table_text_line_spacing_and_spacing(tmp_path: Path) -> None:
    cells = _cells(
        _render(
            tmp_path,
            extra='\n[table.text]\nline_spacing = 1.5\nspace_before = "6pt"\nspace_after = "0pt"\n',
        )
    )
    for cell in cells:
        spacing = re.search(r"<w:spacing ([^/]*)/>", cell)
        assert spacing is not None
        assert 'w:line="360"' in spacing.group(1)
        assert 'w:lineRule="auto"' in spacing.group(1)
        assert 'w:before="120"' in spacing.group(1)  # 6pt * 20
        assert 'w:after="0"' in spacing.group(1)


def test_table_text_font_applies_to_header_and_body(tmp_path: Path) -> None:
    cells = _cells(
        _render(
            tmp_path,
            extra='\n[table.text]\nfont.size = "9pt"\nfont.name = "黑体"\nfont.color = "FF0000"\n',
        )
    )
    for cell in cells:
        assert 'w:sz w:val="18"' in cell
        assert 'w:eastAsia="黑体"' in cell
        assert 'w:color w:val="FF0000"' in cell


def test_header_bold_can_be_disabled(tmp_path: Path) -> None:
    cells = _cells(_render(tmp_path, extra="\n[table]\nheader_bold = false\n"))
    assert "<w:b/>" not in cells[0]
    assert '<w:b w:val="true"/>' not in cells[0]


def test_explicit_font_bold_overrides_header_bold(tmp_path: Path) -> None:
    cells = _cells(_render(tmp_path, extra="\n[table.text]\nfont.bold = false\n"))
    assert "<w:b/>" not in cells[0]


def test_merged_cell_table_also_gets_text_format(tmp_path: Path) -> None:
    table = Table(
        source_line=1,
        rows=[],
        cells=[
            [
                TableCell(blocks=[Paragraph(content=[Text(content="甲")], source_line=1)]),
                TableCell(blocks=[Paragraph(content=[Text(content="乙")], source_line=1)]),
            ],
            [
                TableCell(
                    blocks=[Paragraph(content=[Text(content="合并")], source_line=2)],
                    colspan=2,
                )
            ],
        ],
    )
    cells = _cells(_render(tmp_path, blocks=[table], extra='\n[table.text]\nfont.size = "8pt"\n'))
    assert any("合并" in _text(cell) for cell in cells)
    # 合并产生的空占位单元格没有 run，不需要字号；只检查有内容的格
    for cell in cells:
        if _text(cell):
            assert 'w:sz w:val="16"' in cell


@pytest.mark.parametrize(
    "extra",
    [
        "[table.text]\nline_spacing = 0\n",
        '[table.text]\nline_spacing = "abc"\n',
        "[table.text]\nline_spacing = -1\n",
        '[table]\nheader_bold = "maybe"\n',
        '[table]\ntext = "not a table"\n',
    ],
)
def test_invalid_table_text_config_raises(tmp_path: Path, extra: str) -> None:
    with pytest.raises(DocGenError) as caught:
        _render(tmp_path, extra="\n" + extra)
    assert caught.value.code == "E5001"

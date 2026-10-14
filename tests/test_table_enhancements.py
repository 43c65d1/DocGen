"""表格增强契约（完整版手册 W4）。

- **三线表 / 网格 / 无框**：由 ``[table] style`` 决定
- **重复表头**：``header_repeat = true`` → 表头行加 ``w:tblHeader``
- **固定列宽**：``[table] col_widths = [3, 2, 5]``（相对比例）→ 每列固定 ``w:tcW``
- **合并**：GFM 表格不支持合并，所以从 IR 侧构造 ``TableCell`` 验证渲染；
  列对齐由分隔行 ``:---:`` 决定（IR 仍是纯文本，渲染时读 config）
"""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

from docgen.config import Config, load_config
from docgen.ir import Table, TableCell
from docgen.parser.dfm import parse_dfm
from docgen.render.docx import render_docx_bytes

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

CELLS_CONFIG = """\
config_version = "0.1"

[table]
style = "three_line"
header_repeat = true
col_widths = [3, 2, 5]
"""


def _config(tmp_path: Path, extra: str = CELLS_CONFIG) -> Config:
    path = tmp_path / "config.toml"
    path.write_text(extra, encoding="utf-8")
    return load_config(path)


def _document_xml(tmp_path: Path, markdown: str) -> str:
    data = render_docx_bytes(parse_dfm(markdown), _config(tmp_path))
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return archive.read("word/document.xml").decode("utf-8")


def _xml_from_blocks(tmp_path: Path, blocks: list[object]) -> str:
    data = render_docx_bytes(blocks, _config(tmp_path))  # type: ignore[arg-type]
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return archive.read("word/document.xml").decode("utf-8")


THREE_COL_MD = "| 列 A | 列 B | 列 C |\n| --- | --- | --- |\n| a1 | b1 | c1 |\n| a2 | b2 | c2 |\n"

TABLE_MD = "| 列 A | 列 B |\n| --- | --- |\n| a1 | b1 |\n| a2 | b2 |\n"


# --------------------------------------------------------------------------
# 表格样式
# --------------------------------------------------------------------------
def test_three_line_table_borders(tmp_path: Path) -> None:
    """三线表：上下框 + 表头下框有线，其余内部框线为 none。"""
    document = _document_xml(tmp_path, TABLE_MD)
    assert "<w:tblBorders>" in document
    assert 'w:val="single"' in document
    assert document.count('w:val="none"') >= 3  # left/right/insideV/insideH
    assert "<w:tcBorders>" in document  # 表头下横线


def test_grid_table_style(tmp_path: Path) -> None:
    config = CELLS_CONFIG.replace('style = "three_line"', 'style = "grid"')
    document = _document_xml_with(tmp_path, TABLE_MD, config)
    assert document.count('w:val="single"') >= 4


def _document_xml_with(tmp_path: Path, markdown: str, config_text: str) -> str:
    path = tmp_path / "config2.toml"
    path.write_text(config_text, encoding="utf-8")
    data = render_docx_bytes(parse_dfm(markdown), load_config(path))
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return archive.read("word/document.xml").decode("utf-8")


def test_none_table_style_drops_borders(tmp_path: Path) -> None:
    config = CELLS_CONFIG.replace('style = "three_line"', 'style = "none"')
    document = _document_xml_with(tmp_path, TABLE_MD, config)
    assert 'w:val="none"' in document


def test_header_row_repeats(tmp_path: Path) -> None:
    """跨页时表头重复：首个 ``w:tr`` 里要有 ``w:tblHeader``。"""
    document = _document_xml(tmp_path, TABLE_MD)
    first_row = document.split("<w:tr>")[1]
    assert "tblHeader" in first_row
    # 数据行不该带
    assert "tblHeader" not in document.split("<w:tr>")[2]


def test_header_repeat_can_be_disabled(tmp_path: Path) -> None:
    config = CELLS_CONFIG.replace("header_repeat = true", "header_repeat = false")
    document = _document_xml_with(tmp_path, TABLE_MD, config)
    assert "tblHeader" not in document


def test_fixed_column_widths(tmp_path: Path) -> None:
    """固定列宽：三列按 3:2:5 分配，列宽互不相同且与比例一致。"""
    document = _document_xml(tmp_path, THREE_COL_MD)
    widths = [int(w) for w in re.findall(r'<w:tcW w:type="dxa" w:w="(\d+)"/>', document)]
    assert widths, "没有写入列宽"
    first_row = widths[:3]
    assert first_row[0] > first_row[1] < first_row[2] > first_row[0]


def test_column_widths_are_normalised(tmp_path: Path) -> None:
    """同一列在所有行里宽度一致（列宽按列归一化，不是按单元格）。"""
    document = _document_xml(tmp_path, THREE_COL_MD)
    widths = [int(w) for w in re.findall(r'<w:tcW w:type="dxa" w:w="(\d+)"/>', document)]
    assert len(widths) % 3 == 0
    per_row = [widths[i : i + 3] for i in range(0, len(widths), 3)]
    assert len({tuple(row) for row in per_row}) == 1


# --------------------------------------------------------------------------
# 合并（IR 直接构造，GFM 不支持合并语法）
# --------------------------------------------------------------------------
def _merged_table() -> Table:
    return Table(
        source_line=1,
        rows=[],
        cells=[
            [
                TableCell(blocks=[], colspan=2),
                TableCell(blocks=[], is_merge_continuation=True),
                TableCell(blocks=[]),
            ],
            [
                TableCell(blocks=[], rowspan=2),
                TableCell(blocks=[]),
                TableCell(blocks=[]),
            ],
        ],
    )


def test_merged_cells_use_grid_span_and_v_merge(tmp_path: Path) -> None:
    document = _xml_from_blocks(tmp_path, [_merged_table()])
    assert "<w:gridSpan" in document
    assert 'w:val="2"' in document
    assert "<w:vMerge" in document


# --------------------------------------------------------------------------
# 列对齐（GFM 分隔行）
# --------------------------------------------------------------------------
def test_alignment_markers_are_parsed(tmp_path: Path) -> None:
    table = parse_dfm("| 左 | 中 | 右 |\n| :--- | :---: | ---: |\n| 1 | 2 | 3 |\n")[0]
    assert isinstance(table, Table)
    assert table.alignments == ["left", "center", "right"]


def test_alignment_is_rendered(tmp_path: Path) -> None:
    document = _document_xml(tmp_path, "| 左 | 中 | 右 |\n| :--- | :---: | ---: |\n| 1 | 2 | 3 |\n")
    assert 'w:val="center"' in document
    assert 'w:val="right"' in document


def test_plain_table_has_no_alignment(tmp_path: Path) -> None:
    table = parse_dfm(TABLE_MD)[0]
    assert isinstance(table, Table)
    assert table.alignments == []

"""表格合并语法：``[[merge:2]]`` / ``[[merge:2,3]]``。"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

from docgen.config import Config, load_config
from docgen.ir import Paragraph, Table, Text
from docgen.parser.dfm import parse_dfm
from docgen.render.docx import render_docx_bytes

BASE = 'config_version = "0.1"\n\n[table]\nstyle = "grid"\n'


def _config(tmp_path: Path) -> Config:
    path = tmp_path / "c.toml"
    path.write_text(BASE, encoding="utf-8")
    return load_config(path)


def _table(markdown: str) -> Table:
    blocks = parse_dfm(markdown)
    assert isinstance(blocks[0], Table)
    return blocks[0]


def _document(tmp_path: Path, markdown: str) -> str:
    data = render_docx_bytes(parse_dfm(markdown), _config(tmp_path), base_dir=tmp_path)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return archive.read("word/document.xml").decode("utf-8")


HORIZONTAL = """\
| 项目 | 说明 [[merge:2]] | |
| --- | --- | --- |
| A | B | C |
"""

VERTICAL = """\
| 合并 [[merge:1,2]] | B |
| --- | --- |
| | C |
"""

BOTH = """\
| 合并 [[merge:2,2]] | | B |
| --- | --- | --- |
| | | C |
"""


# --------------------------------------------------------------------------
# 解析
# --------------------------------------------------------------------------
def test_horizontal_merge_structure() -> None:
    table = _table(HORIZONTAL)
    assert table.cells
    origin = table.cells[0][1]
    assert (origin.colspan, origin.rowspan) == (2, 1)
    assert table.cells[0][2].is_merge_continuation
    # 标记本身不进内容
    block = origin.blocks[0]
    assert isinstance(block, Paragraph)
    text = "".join(node.content for node in block.content if isinstance(node, Text))
    assert "merge" not in text and "说明" in text


def test_vertical_merge_structure() -> None:
    table = _table(VERTICAL)
    assert table.cells
    origin = table.cells[0][0]
    assert (origin.colspan, origin.rowspan) == (1, 2)
    assert table.cells[1][0].is_merge_continuation
    assert table.cells[1][1].blocks  # 第二行第二格保留内容


def test_both_span_structure() -> None:
    table = _table(BOTH)
    origin = table.cells[0][0]
    assert (origin.colspan, origin.rowspan) == (2, 2)


def test_no_marker_keeps_old_table_shape() -> None:
    table = _table("| A | B |\n| --- | --- |\n| 1 | 2 |\n")
    assert table.cells == []
    assert table.rows == [["A", "B"], ["1", "2"]]


def test_invalid_merge_spec_degrades_to_plain_cell() -> None:
    table = _table("| A [[merge:abc]] | B |\n| --- | --- |\n| 1 | 2 |\n")
    assert table.cells == []
    assert table.rows[0][0] == "A"


# --------------------------------------------------------------------------
# 渲染
# --------------------------------------------------------------------------
def test_horizontal_merge_render(tmp_path: Path) -> None:
    document = _document(tmp_path, HORIZONTAL)
    assert document.count("<w:gridSpan") == 1
    assert 'w:val="2"' in document
    assert document.count("<w:tc>") == 5  # 3x3 - 1
    assert "[[merge" not in document


def test_vertical_merge_render(tmp_path: Path) -> None:
    document = _document(tmp_path, VERTICAL)
    assert '<w:vMerge w:val="restart"/>' in document
    assert "<w:vMerge/>" in document


def test_both_span_render(tmp_path: Path) -> None:
    document = _document(tmp_path, BOTH)
    assert '<w:gridSpan w:val="2"/>' in document
    assert '<w:vMerge w:val="restart"/>' in document
    assert "<w:vMerge/>" in document
    assert document.count("<w:tc>") == 4  # 3x3 网格 - 2x2 合并掉 3 格


def test_merged_table_keeps_layout_features(tmp_path: Path) -> None:
    config = BASE + 'row_height = "0.8cm"\ncell_vertical_align = "center"\n'
    path = tmp_path / "c.toml"
    path.write_text(config, encoding="utf-8")
    data = render_docx_bytes(parse_dfm(HORIZONTAL), load_config(path), base_dir=tmp_path)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        document = archive.read("word/document.xml").decode("utf-8")
    assert "<w:trHeight" in document
    assert "<w:vAlign" in document

"""表格线：预设之外的**逐边线型/粗细/颜色**、行间横线、斜线表头。

以前只有三线表/网格/无框三个预设，且只写 ``w:val``——线和粗细颜色都不可配，
斜线表头干脆没有。这里守住新增能力，也守住默认观感不变。
"""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

import pytest

from docgen.config import Config, load_config
from docgen.errors import DocGenError
from docgen.ir import DiagonalHeader, Table
from docgen.parser.dfm import parse_dfm
from docgen.render.docx import render_docx_bytes

TABLE_MD = "| A | B |\n| --- | --- |\n| 1 | 2 |\n| 3 | 4 |\n"
BASE = 'config_version = "0.1"\n\n[math]\nengine = "plain"\n'


def _config(tmp_path: Path, extra: str = "") -> Config:
    path = tmp_path / "config.toml"
    path.write_text(BASE + extra, encoding="utf-8")
    return load_config(path)


def _render(tmp_path: Path, markdown: str = TABLE_MD, extra: str = "") -> str:
    data = render_docx_bytes(parse_dfm(markdown), _config(tmp_path, extra))
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return archive.read("word/document.xml").decode("utf-8")


def _tbl_borders(document: str) -> str:
    match = re.search(r"<w:tblBorders>.*?</w:tblBorders>", document, re.DOTALL)
    return match.group(0) if match else ""


# --------------------------------------------------------------------------
# 预设：默认观感不变
# --------------------------------------------------------------------------
def test_three_line_default_is_unchanged(tmp_path: Path) -> None:
    """默认三线表：顶/底 single，其余 none；表头下横线 1pt。"""
    document = _render(tmp_path)
    borders = _tbl_borders(document)
    assert 'w:top w:val="single"' in borders
    assert 'w:bottom w:val="single"' in borders
    assert 'w:left w:val="none"' in borders
    assert 'w:insideH w:val="none"' in borders
    header_bottom = re.search(r"<w:tcBorders>.*?</w:tcBorders>", document, re.DOTALL)
    assert header_bottom is not None
    assert 'w:sz="8"' in header_bottom.group(0)


def test_grid_style_sets_all_edges(tmp_path: Path) -> None:
    borders = _tbl_borders(_render(tmp_path, extra='\n[table]\nstyle = "grid"\n'))
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        assert f'w:{edge} w:val="single"' in borders


def test_none_style_turns_everything_off(tmp_path: Path) -> None:
    borders = _tbl_borders(_render(tmp_path, extra='\n[table]\nstyle = "none"\n'))
    assert 'w:val="none"' in borders
    assert 'w:val="single"' not in borders


# --------------------------------------------------------------------------
# 线宽 / 颜色
# --------------------------------------------------------------------------
def test_line_size_and_color_reach_every_edge(tmp_path: Path) -> None:
    extra = '\n[table]\nstyle = "grid"\nline_size = "1pt"\nline_color = "000000"\n'
    borders = _tbl_borders(_render(tmp_path, extra=extra))
    assert borders.count('w:sz="8"') == 6
    assert borders.count('w:color="000000"') == 6


def test_line_size_accepts_px(tmp_path: Path) -> None:
    """12px = 9pt → sz=72（1/8 磅单位）。"""
    borders = _tbl_borders(_render(tmp_path, extra='\n[table]\nline_size = "12px"\n'))
    assert 'w:sz="72"' in borders


def test_bad_line_size_raises_config_error(tmp_path: Path) -> None:
    config = _config(tmp_path, '\n[table]\nline_size = "fat"\n')
    with pytest.raises(DocGenError) as caught:
        render_docx_bytes(parse_dfm(TABLE_MD), config)
    assert caught.value.code == "E5001"


# --------------------------------------------------------------------------
# custom：逐边线型
# --------------------------------------------------------------------------
def test_custom_edges_override_each_side(tmp_path: Path) -> None:
    extra = (
        "\n[table]\n"
        'style = "custom"\n'
        'edges = { top = "single", bottom = "double", insideH = "dashed" }\n'
    )
    borders = _tbl_borders(_render(tmp_path, extra=extra))
    assert 'w:top w:val="single"' in borders
    assert 'w:bottom w:val="double"' in borders
    assert 'w:insideH w:val="dashed"' in borders
    assert 'w:left w:val="none"' in borders


def test_unknown_custom_edge_raises(tmp_path: Path) -> None:
    extra = '\n[table]\nstyle = "custom"\nedges = { middle = "single" }\n'
    with pytest.raises(DocGenError) as caught:
        render_docx_bytes(parse_dfm(TABLE_MD), _config(tmp_path, extra))
    assert caught.value.code == "E5001"


def test_unknown_table_style_raises(tmp_path: Path) -> None:
    """以前未知 style 会静默退回三线表，现在明确报错。"""
    with pytest.raises(DocGenError) as caught:
        render_docx_bytes(parse_dfm(TABLE_MD), _config(tmp_path, '\n[table]\nstyle = "wat"\n'))
    assert caught.value.code == "E5001"


# --------------------------------------------------------------------------
# 行间横线
# --------------------------------------------------------------------------
def test_row_lines_draw_bottom_border_on_every_row_but_last(tmp_path: Path) -> None:
    document = _render(
        tmp_path,
        "| A |\n| --- |\n| 1 |\n| 2 |\n",
        '\n[table]\nstyle = "none"\nrow_lines = true\n',
    )
    tc_borders = re.findall(r"<w:tcBorders>.*?</w:tcBorders>", document, re.DOTALL)
    # 3 行 → 前两行各有 1 格底线；最后一行不画
    assert len(tc_borders) == 2
    assert all('w:bottom w:val="single"' in item for item in tc_borders)


def test_row_lines_can_use_a_specific_style(tmp_path: Path) -> None:
    document = _render(
        tmp_path,
        "| A |\n| --- |\n| 1 |\n| 2 |\n",
        '\n[table]\nstyle = "none"\nrow_lines = "dashed"\n',
    )
    assert 'w:bottom w:val="dashed"' in document


# --------------------------------------------------------------------------
# 斜线表头
# --------------------------------------------------------------------------
DIAG_MD = "| [[diag:年份;项目]] | 2024 |\n| --- | --- |\n| A | 1 |\n"


def test_diagonal_marker_becomes_ir_node() -> None:
    blocks = parse_dfm(DIAG_MD)
    table = blocks[0]
    assert isinstance(table, Table)
    assert table.cell_nodes[0][0] == [DiagonalHeader(upper="年份", lower="项目")]


def test_diagonal_cell_gets_tl2br_border(tmp_path: Path) -> None:
    document = _render(tmp_path, DIAG_MD, '\n[table]\nline_size = "1pt"\nline_color = "000000"\n')
    tc_borders = re.search(r"<w:tcBorders>.*?</w:tcBorders>", document, re.DOTALL)
    assert tc_borders is not None
    assert 'w:tl2br w:val="single"' in tc_borders.group(0)
    assert 'w:sz="8"' in tc_borders.group(0)


def test_diagonal_cell_has_two_aligned_paragraphs(tmp_path: Path) -> None:
    document = _render(tmp_path, DIAG_MD)
    first = re.search(r"<w:p>.*?</w:p>", document, re.DOTALL)
    assert first is not None
    assert '<w:jc w:val="right"/>' in first.group(0)
    assert "年份" in first.group(0)
    # 第二段左对齐放「项目」
    second = re.search(r"<w:p>(?:(?!<w:p>).)*?项目.*?</w:p>", document, re.DOTALL)
    assert second is not None
    assert '<w:jc w:val="left"/>' in second.group(0)


def test_diagonal_border_order_is_schema_valid(tmp_path: Path) -> None:
    """``w:bottom`` 必须在 ``w:tl2br`` 之前（CT_TcBorders 是 sequence）。"""
    document = _render(tmp_path, DIAG_MD)
    tc_borders = re.search(r"<w:tcBorders>.*?</w:tcBorders>", document, re.DOTALL)
    assert tc_borders is not None
    body = tc_borders.group(0)
    assert body.index("<w:bottom") < body.index("<w:tl2br")


def test_diagonal_outside_table_degrades_to_text(tmp_path: Path) -> None:
    """斜线标记写在表格外时不能崩，也不能丢文字。"""
    document = _render(tmp_path, "正文 [[diag:上;下]] 结束。\n")
    assert "上" in document and "下" in document

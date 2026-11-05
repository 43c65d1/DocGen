"""表格表头排版：表头不孤行（与首行数据同页）、表头行不拆分、跨页重复。

实测（Word 2016+，宋体 11pt / 1.5 倍行距，A4）：
表头恰好卡在页底时（填充 17 段），修复前「表头在第 1 页、首行数据在第 2 页」；
给表头段落写 `w:keepNext` 后两者都到第 2 页。规范依据：学位论文/学术出版
普遍要求表头不得单独留在页底（表头等同标题类元素）。
"""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

import pytest

from docgen.config import Config, load_config
from docgen.errors import DocGenError
from docgen.ir import Table
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


def _rows(document: str) -> list[str]:
    return re.findall(r"<w:tr>.*?</w:tr>", document, re.DOTALL)


# --------------------------------------------------------------------------
# 默认行为
# --------------------------------------------------------------------------
def test_header_row_cannot_split_and_repeats(tmp_path: Path) -> None:
    header = _rows(_render(tmp_path))[0]
    trpr = re.search(r"<w:trPr>.*?</w:trPr>", header, re.DOTALL)
    assert trpr is not None
    assert "<w:cantSplit/>" in trpr.group(0)
    assert "<w:tblHeader/>" in trpr.group(0)
    # CT_TrPr 是 sequence：cantSplit 必须在 tblHeader 之前
    assert trpr.group(0).index("<w:cantSplit/>") < trpr.group(0).index("<w:tblHeader/>")


def test_header_paragraphs_keep_with_next(tmp_path: Path) -> None:
    """表头单元格里每个段落都要 keepNext，否则表头会单独留在页底。"""
    header = _rows(_render(tmp_path))[0]
    assert header.count("<w:keepNext/>") == 2  # 2 列 → 2 个表头段落


def test_header_keep_with_body_can_be_disabled(tmp_path: Path) -> None:
    header = _rows(_render(tmp_path, extra="\n[table]\nheader_keep_with_body = false\n"))[0]
    assert "<w:keepNext/>" not in header
    assert "<w:cantSplit/>" in header  # 关掉的只是「同页」，不拆行仍保留


def test_header_repeat_can_be_disabled(tmp_path: Path) -> None:
    header = _rows(_render(tmp_path, extra="\n[table]\nheader_repeat = false\n"))[0]
    assert "<w:tblHeader/>" not in header
    assert "<w:cantSplit/>" in header


def test_single_row_table_is_not_bound_to_following_text(tmp_path: Path) -> None:
    """只有一行（纯表头）时不该 keepNext：否则会和表后正文绑在一起被整体推页。"""
    document = _render(tmp_path, "| A | B |\n| --- | --- |\n")
    header = _rows(document)[0]
    assert "<w:keepNext/>" not in header


def test_header_keep_with_body_rejects_non_boolean(tmp_path: Path) -> None:
    config = _config(tmp_path, '\n[table]\nheader_keep_with_body = "maybe"\n')
    with pytest.raises(DocGenError) as caught:
        render_docx_bytes(parse_dfm(TABLE_MD), config)
    assert caught.value.code == "E5001"


# --------------------------------------------------------------------------
# 与合并单元格路径共用同一套表头行为
# --------------------------------------------------------------------------
def test_cell_table_path_also_keeps_header(tmp_path: Path) -> None:
    """合并单元格路径（``Table.cells``）也要走同一套表头行为。"""
    from docgen.ir import Paragraph, TableCell, Text

    def cell(text: str) -> TableCell:
        return TableCell(blocks=[Paragraph(content=[Text(content=text)], source_line=1)])

    table = Table(
        rows=[["合并", "B"], ["1", "2"]],
        cells=[[cell("合并"), cell("B")], [cell("1"), cell("2")]],
        source_line=1,
    )
    data = render_docx_bytes([table], _config(tmp_path))
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        document = archive.read("word/document.xml").decode("utf-8")
    header = _rows(document)[0]
    assert "<w:cantSplit/>" in header
    assert "<w:keepNext/>" in header

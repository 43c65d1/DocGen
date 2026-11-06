"""表格数值列：小数点 / 个位对齐（``[table] decimal_align``）。

Word 实测（宋体 11pt，A4）：
- 小数行「小数点」x 一致（486）；
- 整数行「末位」与小数行「个位」x 一致（477）。
实现用「right tab + left tab 同一位置」拆分整数/小数——Word 的
``w:tab w:val="decimal"`` 在**表格单元格**里不生效（正文段落才生效）。
"""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

import pytest

from docgen.config import Config, load_config
from docgen.errors import DocGenError
from docgen.parser.dfm import parse_dfm
from docgen.render.docx import render_docx_bytes

BASE = 'config_version = "0.1"\n\n[math]\nengine = "plain"\n'
TABLE_MD = "| 项目 | 金额 |\n| --- | --- |\n| 甲 | 12.34 |\n| 乙 | 5 |\n| 丙 | N/A |\n"


def _config(tmp_path: Path, extra: str = "") -> Config:
    path = tmp_path / "config.toml"
    path.write_text(BASE + extra, encoding="utf-8")
    return load_config(path)


def _render(tmp_path: Path, extra: str = "") -> str:
    data = render_docx_bytes(parse_dfm(TABLE_MD), _config(tmp_path, extra))
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return archive.read("word/document.xml").decode("utf-8")


def _rows(document: str) -> list[str]:
    return re.findall(r"<w:tr>.*?</w:tr>", document, re.DOTALL)


def test_no_decimal_align_by_default(tmp_path: Path) -> None:
    document = _render(tmp_path)
    assert "<w:tabs>" not in document


def test_decimal_column_uses_right_and_left_tab(tmp_path: Path) -> None:
    rows = _rows(_render(tmp_path, "\n[table]\ndecimal_align = [2]\n"))
    # 表头不参与对齐
    assert "<w:tabs>" not in rows[0]
    # 12.34：right tab + left tab 同位置，拆成「12」与「.34」
    assert '<w:tab w:val="right" w:pos="3540"/>' in rows[1]
    assert '<w:tab w:val="left" w:pos="3540"/>' in rows[1]
    assert "<w:t>12</w:t>" in rows[1]
    assert "<w:t>.34</w:t>" in rows[1]


def test_integer_cell_uses_right_tab_only(tmp_path: Path) -> None:
    row = _rows(_render(tmp_path, "\n[table]\ndecimal_align = [2]\n"))[2]
    assert '<w:tab w:val="right" w:pos="3540"/>' in row
    assert '<w:tab w:val="left"' not in row
    assert "<w:t>5</w:t>" in row


def test_non_numeric_cell_is_left_untouched(tmp_path: Path) -> None:
    row = _rows(_render(tmp_path, "\n[table]\ndecimal_align = [2]\n"))[3]
    assert "<w:tabs>" not in row
    assert "N/A" in row


def test_negative_and_zero_decimals(tmp_path: Path) -> None:
    md = "| 项 | 值 |\n| --- | --- |\n| a | -0.5 |\n| b | 0.005 |\n"
    data = render_docx_bytes(parse_dfm(md), _config(tmp_path, "\n[table]\ndecimal_align = [2]\n"))
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        doc = archive.read("word/document.xml").decode("utf-8")
    rows = _rows(doc)
    assert "<w:t>-0</w:t>" in rows[1]
    assert "<w:t>.5</w:t>" in rows[1]
    assert "<w:t>0</w:t>" in rows[2]
    assert "<w:t>.005</w:t>" in rows[2]


@pytest.mark.parametrize(
    "extra",
    [
        "\n[table]\ndecimal_align = 2\n",  # 不是数组
        '\n[table]\ndecimal_align = ["2"]\n',  # 字符串
        "\n[table]\ndecimal_align = [9]\n",  # 列号越界
    ],
)
def test_invalid_decimal_align_raises(tmp_path: Path, extra: str) -> None:
    with pytest.raises(DocGenError) as caught:
        render_docx_bytes(parse_dfm(TABLE_MD), _config(tmp_path, extra))
    assert caught.value.code == "E5001"

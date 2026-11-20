"""逐表宽度：``[[table-width:...]]`` / ``[[col-widths:...]]``。"""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

import pytest

from docgen.config import Config, load_config
from docgen.errors import E_CONFIG, DocGenError
from docgen.ir import Paragraph, TableOption
from docgen.parser.dfm import parse_dfm
from docgen.render.docx import render_docx_bytes

BASE = 'config_version = "0.1"\n'

DOC = """\\
| 项目 | 金额 |
| --- | --- |
| A | 10 |

| [[table-width:80%]] 项目 | 金额 |
| --- | --- |
| B | 20 |

| [[col-widths:1,3]] 项目 | 金额 |
| --- | --- |
| C | 30 |

| [[table-width:50%]] 合并 | 说明 [[merge:2]] | |
| --- | --- | --- |
| D | E | F |
"""


def _config(tmp_path: Path, extra: str = "") -> Config:
    path = tmp_path / "c.toml"
    path.write_text(BASE + extra, encoding="utf-8")
    return load_config(path)


def _document(tmp_path: Path, extra: str = "", markdown: str = DOC) -> str:
    data = render_docx_bytes(parse_dfm(markdown), _config(tmp_path, extra), base_dir=tmp_path)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return archive.read("word/document.xml").decode("utf-8")


def _tables(document: str) -> list[str]:
    return re.findall(r"<w:tbl>.*?</w:tbl>", document, re.DOTALL)


def _total_width(tbl: str) -> int:
    tag = re.search(r"<w:tblW[^>]*/>", tbl)
    assert tag is not None, "表格没有 tblW"
    attrs = dict(re.findall(r'w:(\w+)="([^"]*)"', tag.group(0)))
    assert attrs.get("type") == "dxa", "表格没有固定总宽"
    return int(attrs["w"])


def _grid(tbl: str) -> list[int]:
    return [int(value) for value in re.findall(r'<w:gridCol w:w="(\d+)"', tbl)]


def _all_text(document: str) -> str:
    return "".join(re.findall(r"<w:t(?: [^>]*)?>(.*?)</w:t>", document, re.DOTALL))


def test_parse_table_option_marker() -> None:
    blocks = parse_dfm("[[table-width:80%]]\n")
    assert isinstance(blocks[0], Paragraph)
    option = next(node for node in blocks[0].content if isinstance(node, TableOption))
    assert option.name == "table-width"
    assert option.value == "80%"


def test_default_table_uses_content_width(tmp_path: Path) -> None:
    document = _document(tmp_path)
    first = _tables(document)[0]
    assert _total_width(first) == sum(_grid(first))


def test_per_table_percent_width(tmp_path: Path) -> None:
    document = _document(tmp_path)
    tables = _tables(document)
    base = _total_width(tables[0])
    narrow = _total_width(tables[1])
    assert abs(narrow - round(base * 0.8)) <= 1
    assert sum(_grid(tables[1])) == narrow


def test_per_table_absolute_width(tmp_path: Path) -> None:
    markdown = "| [[table-width:12cm]] A | B |\n| --- | --- |\n| 1 | 2 |\n"
    tables = _tables(_document(tmp_path, markdown=markdown))
    # 12cm = 12 / 2.54 * 1440 缇
    assert abs(_total_width(tables[0]) - 6803) <= 2


def test_per_table_col_widths(tmp_path: Path) -> None:
    document = _document(tmp_path)
    tables = _tables(document)
    base = _total_width(tables[0])
    equal = _grid(tables[0])
    ratio = _grid(tables[2])
    assert abs(equal[0] - equal[1]) <= 1
    assert ratio[1] > ratio[0] * 2.5
    assert abs(sum(ratio) - base) <= 1


def test_marker_works_on_merged_cell_table(tmp_path: Path) -> None:
    document = _document(tmp_path)
    tables = _tables(document)
    base = _total_width(tables[0])
    merged = _total_width(tables[3])
    assert abs(merged - round(base * 0.5)) <= 1


def test_markers_are_not_rendered(tmp_path: Path) -> None:
    text = _all_text(_document(tmp_path))
    assert "table-width" not in text
    assert "col-widths" not in text


def test_per_table_width_wins_over_autofit(tmp_path: Path) -> None:
    markdown = (
        "| 项目 | 金额 |\n| --- | --- |\n| A | 10 |\n\n"
        "| [[table-width:60%]] 项目 | 金额 |\n| --- | --- |\n| B | 20 |\n"
    )
    tables = _tables(_document(tmp_path, "\n[table]\nautofit = true\n", markdown=markdown))
    assert 'w:type="autofit"' in tables[0]
    assert 'w:type="fixed"' in tables[1]


def test_invalid_table_width_reports_config_error(tmp_path: Path) -> None:
    markdown = "| [[table-width:abc]] A | B |\n| --- | --- |\n| 1 | 2 |\n"
    with pytest.raises(DocGenError) as error:
        _document(tmp_path, markdown=markdown)
    assert error.value.code == E_CONFIG


def test_invalid_col_widths_reports_config_error(tmp_path: Path) -> None:
    markdown = "| [[col-widths:3,x]] A | B |\n| --- | --- |\n| 1 | 2 |\n"
    with pytest.raises(DocGenError) as error:
        _document(tmp_path, markdown=markdown)
    assert error.value.code == E_CONFIG

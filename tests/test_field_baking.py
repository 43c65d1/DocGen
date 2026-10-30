"""域缓存值（``w:fldChar separate`` 后的结果）必须**烘焙成真实编号**。

Word 打开文档时会按 ``updateFields`` 重算域，所以缓存值写错也看不出来；
但 WPS / Office 预览 / 网页版 / 解包 XML 的脚本只认缓存值——
原先所有域都写死 ``"1"``，于是整篇图号都显示「图 1」（实测反馈）。

另外 ``w:updateFields`` 必须按 ``CT_Settings`` 的 schema 顺序插入，
append 到末尾会被严格实现忽略（那样连 Word 都不更新域）。
"""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

import pytest

from docgen.config import Config, load_config
from docgen.ir import NamedBlock
from docgen.numbering import baked_fields, caption_counters
from docgen.parser.dfm import parse_dfm
from docgen.render.docx import render_docx_bytes

BASE = 'config_version = "0.1"\n\n[math]\nengine = "plain"\n'


def _config(tmp_path: Path) -> Config:
    path = tmp_path / "config.toml"
    path.write_text(BASE, encoding="utf-8")
    return load_config(path)


def _parts(tmp_path: Path, markdown: str) -> tuple[str, str]:
    """返回 (document.xml, settings.xml)。"""
    data = render_docx_bytes(parse_dfm(markdown), _config(tmp_path))
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return (
            archive.read("word/document.xml").decode("utf-8"),
            archive.read("word/settings.xml").decode("utf-8"),
        )


def _fields(document: str) -> list[tuple[str, str]]:
    """抽出 ``(域指令, 缓存结果)``。缓存结果是 ``separate`` 之后第一个 ``w:t``。"""
    pattern = (
        r"<w:instrText[^>]*>(.*?)</w:instrText>"
        r'.*?<w:fldChar w:fldCharType="separate"/>'
        r".*?<w:t[^>]*>(.*?)</w:t>"
    )
    return [(instr.strip(), cached) for instr, cached in re.findall(pattern, document, re.DOTALL)]


def _cached_for(document: str, prefix: str) -> list[str]:
    return [cached for instr, cached in _fields(document) if instr.startswith(prefix)]


# --------------------------------------------------------------------------
# 题注：SEQ 缓存值 = 真实序号
# --------------------------------------------------------------------------
THREE_FIGURES = """\
\\begin{caption #fig:a}
第一张
\\end{caption}

见 [[ref:fig:a]]。

\\begin{caption #fig:b}
第二张
\\end{caption}

见 [[ref:fig:b]]。

\\begin{caption #fig:c}
第三张
\\end{caption}

见 [[ref:fig:c]]。
"""


def test_caption_seq_cache_is_the_real_number(tmp_path: Path) -> None:
    document, _ = _parts(tmp_path, THREE_FIGURES)
    assert _cached_for(document, "SEQ") == ["1", "2", "3"]
    assert _cached_for(document, "REF") == ["1", "2", "3"]


def test_caption_kinds_are_counted_independently(tmp_path: Path) -> None:
    markdown = (
        "\\begin{caption #fig:1}\n图一\n\\end{caption}\n\n"
        "\\begin{table #tab:1}\n表一\n\\end{table}\n\n"
        "\\begin{caption #fig:2}\n图二\n\\end{caption}\n\n"
        "见图 [[ref:fig:2]] 与表 [[ref:tab:1]]。\n"
    )
    document, _ = _parts(tmp_path, markdown)
    assert _cached_for(document, "SEQ") == ["1", "1", "2"]
    assert _cached_for(document, "REF") == ["2", "1"]


def test_forward_reference_gets_the_future_number(tmp_path: Path) -> None:
    """引用出现在题注之前也要烘焙正确——渲染前先把整篇算好。"""
    markdown = "先见 [[ref:fig:late]]。\n\n\\begin{caption #fig:late}\n后面的图\n\\end{caption}\n"
    document, _ = _parts(tmp_path, markdown)
    assert _cached_for(document, "REF") == ["1"]


def test_equation_reference_keeps_parentheses(tmp_path: Path) -> None:
    """编号公式的书签包住 ``(N)``，所以 REF 的缓存值也要带括号。"""
    markdown = (
        "\\begin{equation #eq:main number=1}\n$$E=mc^2$$\n\\end{equation}\n\n"
        "公式 [[ref:eq:main]] 见上。\n"
    )
    document, _ = _parts(tmp_path, markdown)
    assert _cached_for(document, "REF") == ["(1)"]


def test_baked_fields_helper_matches_rendered_document(tmp_path: Path) -> None:
    """辅助函数的输出要和渲染结果一致（避免两处逻辑漂移）。"""
    blocks = parse_dfm(THREE_FIGURES)
    assert baked_fields(blocks) == {"fig:a": "1", "fig:b": "2", "fig:c": "3"}
    assert caption_counters(blocks) == {"fig:a": 1, "fig:b": 2, "fig:c": 3}
    assert all(isinstance(block, NamedBlock) for block in blocks if isinstance(block, NamedBlock))


def test_unnumbered_equation_is_not_baked(tmp_path: Path) -> None:
    """无 ``number`` 的公式没有编号，不该凭空产生缓存值。"""
    blocks = parse_dfm("\\begin{equation #eq:x}\n$$x=1$$\n\\end{equation}\n")
    assert baked_fields(blocks) == {}


# --------------------------------------------------------------------------
# TOC / PAGE 不做烘焙（无法在渲染期算出，仍由查看器更新）
# --------------------------------------------------------------------------
def test_toc_field_keeps_its_placeholder(tmp_path: Path) -> None:
    document, _ = _parts(tmp_path, "[[toc]]\n")
    assert _cached_for(document, "TOC") == ["按 F9 更新目录"]


# --------------------------------------------------------------------------
# settings.xml：updateFields 必须在 schema 位置上
# --------------------------------------------------------------------------
def test_update_fields_is_schema_ordered(tmp_path: Path) -> None:
    """``w:updateFields`` 不能 append 到 settings 末尾。

    并且整份 settings 的子元素都要按 ``CT_Settings`` 顺序排列——
    这条同时守住「以后再加 settings 元素」的情况。
    """
    from docgen.render.ooxml import CHILD_ORDER

    _, settings = _parts(tmp_path, "正文\n")
    body = settings.split("?>", 1)[1]
    children = re.findall(r"<(w:[A-Za-z]+)[ />]", body)
    assert "w:updateFields" in children

    order = CHILD_ORDER["w:settings"]
    ranks = [order.index(name) for name in children if name in order]
    assert ranks == sorted(ranks), f"settings 顺序不对：{children}"


@pytest.mark.parametrize("markdown", ["正文\n", "\\begin{caption #f:1}\n图\n\\end{caption}\n"])
def test_update_fields_is_present_once(tmp_path: Path, markdown: str) -> None:
    _, settings = _parts(tmp_path, markdown)
    assert settings.count("w:updateFields") == 1

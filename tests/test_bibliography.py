"""文献引用（方案 A）：``[[cite:...]]`` + 文献库 + ``[[bibliography]]``。

顺序编码制（GB/T 7714 风格）：编号按首次出现顺序，构建期烘焙；
文献表由 TOML 文献库生成，不依赖 Word 引文功能。
"""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

import pytest

from docgen.bibliography import (
    citation_text,
    collect_citations,
    format_reference,
    has_bibliography_marker,
    load_references,
    plan_bibliography,
    validate_bibliography,
)
from docgen.config import Config, load_config
from docgen.errors import DocGenError
from docgen.ir import Bibliography, Cite
from docgen.parser.dfm import parse_dfm
from docgen.render.docx import render_docx_bytes

BASE = 'config_version = "0.1"\n\n[math]\nengine = "plain"\n'
REFS = """\
[zhang2024]
type = "article"
author = ["张三", "李四"]
title = "中文排版中的行首禁则研究"
journal = "排版学报"
year = "2024"
volume = "12"
issue = "3"
pages = "45-52"

[wang2023]
type = "book"
author = "王五"
title = "现代文档工程"
place = "北京"
publisher = "科学出版社"
year = "2023"

[zhao2022]
type = "online"
author = "赵六"
title = "DocGen 项目主页"
url = "https://example.com/docgen"
date = "2022-05-01"
cited = "2024-01-02"
"""


def _config(tmp_path: Path, extra: str = "") -> Config:
    path = tmp_path / "config.toml"
    path.write_text(BASE + extra, encoding="utf-8")
    return load_config(path)


def _refs(tmp_path: Path) -> Path:
    path = tmp_path / "refs.toml"
    path.write_text(REFS, encoding="utf-8")
    return path


# --------------------------------------------------------------------------
# 解析
# --------------------------------------------------------------------------
def test_parse_cite_and_bibliography() -> None:
    blocks = parse_dfm("引用[[cite:a,b]]。\n\n[[bibliography]]\n")
    paragraph = blocks[0]
    assert isinstance(paragraph, type(blocks[0]))
    cites = [node for node in getattr(paragraph, "content", []) if isinstance(node, Cite)]
    assert cites and cites[0].keys == ("a", "b")
    assert isinstance(blocks[1], Bibliography)
    assert has_bibliography_marker(blocks) is True


# --------------------------------------------------------------------------
# 编号文本
# --------------------------------------------------------------------------
def test_citation_text_basic_and_ranges() -> None:
    numbers = {"a": 1, "b": 2, "c": 3, "d": 4, "e": 5}
    assert citation_text(("a",), numbers) == "[1]"
    assert citation_text(("b", "a"), numbers) == "[1,2]"
    assert citation_text(("a", "b", "c"), numbers) == "[1-3]"
    assert citation_text(("a", "b", "c", "e"), numbers) == "[1-3,5]"
    assert citation_text(("a", "a", "a"), numbers) == "[1]"


# --------------------------------------------------------------------------
# 文献库
# --------------------------------------------------------------------------
def test_load_references(tmp_path: Path) -> None:
    references = load_references(_refs(tmp_path))
    assert references["zhang2024"]["type"] == "article"
    assert references["wang2023"]["author"] == "王五"


def test_load_references_rejects_broken_toml(tmp_path: Path) -> None:
    bad = tmp_path / "bad.toml"
    bad.write_text("[x\n", encoding="utf-8")
    with pytest.raises(DocGenError) as caught:
        load_references(bad)
    assert caught.value.code == "E5001"


def test_load_references_rejects_non_table_entry(tmp_path: Path) -> None:
    bad = tmp_path / "bad.toml"
    bad.write_text('title = "not a table"\n', encoding="utf-8")
    with pytest.raises(DocGenError) as caught:
        load_references(bad)
    assert caught.value.code == "E5001"


# --------------------------------------------------------------------------
# 编号与条目
# --------------------------------------------------------------------------
def test_plan_numbers_by_first_appearance(tmp_path: Path) -> None:
    blocks = parse_dfm("A[[cite:wang2023]] B[[cite:zhang2024]] C[[cite:wang2023,zhang2024]]。\n")
    plan = plan_bibliography(blocks, _config(tmp_path), refs=_refs(tmp_path))
    assert plan is not None
    assert plan.numbers == {"wang2023": 1, "zhang2024": 2}
    assert plan.entries[0].startswith("王五. 现代文档工程[M]")
    assert plan.entries[1].startswith("张三, 李四. 中文排版中的行首禁则研究[J]")


def test_plan_missing_refs_file_raises(tmp_path: Path) -> None:
    blocks = parse_dfm("引用[[cite:a]]。\n")
    with pytest.raises(DocGenError) as caught:
        plan_bibliography(blocks, _config(tmp_path))
    assert caught.value.code == "E5001"


def test_plan_unknown_key_raises(tmp_path: Path) -> None:
    blocks = parse_dfm("引用[[cite:nobody]]。\n")
    with pytest.raises(DocGenError) as caught:
        plan_bibliography(blocks, _config(tmp_path), refs=_refs(tmp_path))
    assert caught.value.code == "E5004"


def test_plan_empty_cite_raises(tmp_path: Path) -> None:
    blocks = parse_dfm("引用[[cite:]]。\n")
    with pytest.raises(DocGenError) as caught:
        plan_bibliography(blocks, _config(tmp_path), refs=_refs(tmp_path))
    assert caught.value.code == "E4001"


def test_collect_citations_includes_tables() -> None:
    markdown = "| a |\n| --- |\n| [[cite:zhang2024]] |\n"
    blocks = parse_dfm(markdown)
    assert ("zhang2024", blocks[0].source_line) in collect_citations(blocks)


# --------------------------------------------------------------------------
# GB/T 7714 格式化
# --------------------------------------------------------------------------
def test_format_article() -> None:
    entry = {
        "type": "article",
        "author": ["张三", "李四"],
        "title": "标题",
        "journal": "期刊",
        "year": "2024",
        "volume": "12",
        "issue": "3",
        "pages": "45-52",
    }
    assert format_reference(entry, 1) == "张三, 李四. 标题[J]. 期刊, 2024, 12(3): 45-52."


def test_format_book_thesis_standard_conference() -> None:
    assert (
        format_reference(
            {
                "type": "book",
                "author": "王五",
                "title": "书名",
                "place": "北京",
                "publisher": "科学出版社",
                "year": "2023",
            },
            1,
        )
        == "王五. 书名[M]. 北京: 科学出版社, 2023."
    )
    assert (
        format_reference(
            {
                "type": "thesis",
                "author": "李四",
                "title": "论文",
                "school": "某大学",
                "year": "2022",
            },
            1,
        )
        == "李四. 论文[D]. 某大学, 2022."
    )
    assert (
        format_reference(
            {
                "type": "standard",
                "number": "GB/T 7714—2015",
                "title": "信息与文献 参考文献著录规则",
                "year": "2015",
            },
            1,
        )
        == "GB/T 7714—2015 信息与文献 参考文献著录规则[S]. 2015."
    )
    assert (
        format_reference(
            {
                "type": "conference",
                "author": "赵六",
                "title": "会议论文",
                "conference": "某会议",
                "place": "上海",
                "publisher": "出版社",
                "year": "2021",
                "pages": "1-8",
            },
            1,
        )
        == "赵六. 会议论文[C]//某会议. 上海: 出版社, 2021: 1-8."
    )


def test_format_online_and_doi() -> None:
    assert (
        format_reference(
            {
                "type": "online",
                "author": "赵六",
                "title": "主页",
                "url": "https://example.com",
                "date": "2022-05-01",
                "cited": "2024-01-02",
            },
            1,
        )
        == "赵六. 主页[EB/OL]. (2022-05-01)[2024-01-02]. https://example.com."
    )
    assert format_reference({"type": "article", "title": "T", "doi": "10.1/x"}, 1).endswith(
        "DOI: 10.1/x."
    )


# --------------------------------------------------------------------------
# 校验
# --------------------------------------------------------------------------
def test_validate_catches_unknown_and_duplicate_marker(tmp_path: Path) -> None:
    blocks = parse_dfm("引用[[cite:nobody]]。\n\n[[bibliography]]\n\n[[bibliography]]\n")
    errors = validate_bibliography(
        blocks,
        _config(tmp_path),
        source=tmp_path / "doc.md",
        base_dir=tmp_path,
        refs=_refs(tmp_path),
    )
    codes = [err.code for err in errors]
    assert "E4001" in codes  # 重复标记
    assert "E5004" in codes  # 未知 key


def test_validate_catches_missing_library(tmp_path: Path) -> None:
    blocks = parse_dfm("引用[[cite:a]]。\n")
    errors = validate_bibliography(
        blocks, _config(tmp_path), source=tmp_path / "doc.md", base_dir=tmp_path
    )
    assert errors and errors[0].code == "E5001"


def test_chinese_reference_key(tmp_path: Path) -> None:
    """条目名/作者用中文可以用：TOML 非 ASCII key 加引号，``[[cite:]]`` 直接写。"""
    refs = tmp_path / "refs.toml"
    refs.write_text(
        '["张三2024"]\ntype = "article"\nauthor = ["张三"]\ntitle = "中文条目"\n'
        'journal = "期刊"\nyear = "2024"\n',
        encoding="utf-8",
    )
    blocks = parse_dfm("引用[[cite:张三2024]]。\n\n[[bibliography]]\n")
    plan = plan_bibliography(blocks, _config(tmp_path), refs=refs)
    assert plan is not None
    assert plan.numbers == {"张三2024": 1}
    assert plan.entries[0].startswith("张三. 中文条目[J]")

    data = render_docx_bytes(parse_dfm("引用[[cite:张三2024]]。\n"), _config(tmp_path), refs=refs)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        text = "".join(
            re.findall(
                r"<w:t(?: [^>]*)?>(.*?)</w:t>",
                archive.read("word/document.xml").decode(),
                re.DOTALL,
            )
        )
    assert "[1]" in text and "张三" in text


# --------------------------------------------------------------------------
# 渲染
# --------------------------------------------------------------------------
def _render(tmp_path: Path, markdown: str, refs: Path | None = None, extra: str = "") -> str:
    data = render_docx_bytes(
        parse_dfm(markdown),
        _config(tmp_path, extra),
        base_dir=tmp_path,
        refs=refs,
    )
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return archive.read("word/document.xml").decode("utf-8")


def test_render_citations_and_bibliography(tmp_path: Path) -> None:
    document = _render(
        tmp_path,
        "引用[[cite:zhang2024]]与[[cite:wang2023,zhao2022]]。\n\n[[bibliography]]\n",
        _refs(tmp_path),
    )
    texts = re.findall(r"<w:t(?: [^>]*)?>(.*?)</w:t>", document, re.DOTALL)
    joined = "".join(texts)
    assert "[1]" in joined and "[2,3]" in joined
    assert "参考文献" in joined
    assert "张三, 李四" in joined and "王五" in joined
    # 参考文献标题取消编号：numId=0
    assert 'w:numId w:val="0"' in document


def test_render_auto_appends_without_marker(tmp_path: Path) -> None:
    document = _render(tmp_path, "引用[[cite:zhang2024]]。\n", _refs(tmp_path))
    joined = "".join(re.findall(r"<w:t(?: [^>]*)?>(.*?)</w:t>", document, re.DOTALL))
    assert "参考文献" in joined
    assert "张三, 李四" in joined


def test_config_bibliography_file_is_relative_to_input(tmp_path: Path) -> None:
    _refs(tmp_path)
    document = _render(
        tmp_path,
        "引用[[cite:zhang2024]]。\n",
        None,
        '\n[bibliography]\nfile = "refs.toml"\ntitle = "参 考 文 献"\n',
    )
    joined = "".join(re.findall(r"<w:t(?: [^>]*)?>(.*?)</w:t>", document, re.DOTALL))
    assert "参 考 文 献" in joined


def test_render_without_citations_has_no_bibliography(tmp_path: Path) -> None:
    document = _render(tmp_path, "没有引用。\n")
    joined = "".join(re.findall(r"<w:t(?: [^>]*)?>(.*?)</w:t>", document, re.DOTALL))
    assert "参考文献" not in joined

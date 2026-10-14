"""OOXML 结构校验的契约（防「Word 打不开」）。

这一层是为了补上「XML 合法 ≠ Word 能打开」的缺口：
``w:fldChar`` 直接挂在 ``w:p`` 下时 XML 解析完全正常，但 Word 会拒收整份文档。
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from docgen.config import Config, load_config
from docgen.parser.dfm import parse_dfm
from docgen.render.docx import render_docx_bytes
from docgen.render.ooxml_check import validate_document_xml, validate_parts

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

CONFIG_TEXT = """\
config_version = "0.1"

[math]
engine = "plain"
"""


def _config(tmp_path: Path) -> Config:
    path = tmp_path / "config.toml"
    path.write_text(CONFIG_TEXT, encoding="utf-8")
    return load_config(path)


def _parts(tmp_path: Path, markdown: str) -> dict[str, bytes]:
    data = render_docx_bytes(parse_dfm(markdown), _config(tmp_path))
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


# --------------------------------------------------------------------------
# 校验器本身
# --------------------------------------------------------------------------
def test_validator_accepts_minimal_document() -> None:
    xml = (
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body><w:p><w:pPr/><w:r><w:t>x</w:t></w:r></w:p></w:body></w:document>"
    )
    assert validate_document_xml(xml) == []


def test_validator_rejects_bare_fld_char() -> None:
    """这正是导致 Word 打不开的写法：域元素没包在 run 里。"""
    xml = (
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:body><w:p><w:fldChar w:fldCharType="begin"/></w:p></w:body></w:document>'
    )
    problems = validate_document_xml(xml)
    assert problems
    assert "必须包在 <w:r> 里" in problems[0]


def test_validator_rejects_bare_text() -> None:
    xml = (
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body><w:p><w:t>x</w:t></w:p></w:body></w:document>"
    )
    assert any("必须包在 <w:r> 里" in problem for problem in validate_document_xml(xml))


def test_validator_rejects_p_pr_not_first() -> None:
    xml = (
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body><w:p><w:r><w:t>x</w:t></w:r><w:pPr/></w:p></w:body></w:document>"
    )
    assert any("第一个子元素" in problem for problem in validate_document_xml(xml))


def test_validator_flags_empty_run() -> None:
    xml = (
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body><w:p><w:r/></w:p></w:body></w:document>"
    )
    assert any("空 run" in problem for problem in validate_document_xml(xml))


def test_validator_rejects_bad_table_child() -> None:
    xml = (
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body><w:tbl><w:p/></w:tbl></w:body></w:document>"
    )
    assert any("不允许的子元素" in problem for problem in validate_document_xml(xml))


# --------------------------------------------------------------------------
# 真实渲染产物（含全部特性）必须通过
# --------------------------------------------------------------------------
FEATURES = (
    "# 标题\n\n段落 **粗体** H~2~O E=mc^2^\n",
    "\\begin{caption #fig:1}\n图题\n\\end{caption}\n\n见图 [[ref:fig:1]]。\n",
    "[[toc]]\n\n# 标题\n",
    "\\begin{equation #eq:1 number=1}\n$$x=1$$\n\\end{equation}\n\n见式 [[ref:eq:1]]。\n",
    "- 项\n\n```python\nprint(1)\n```\n\n> 引用\n",
    "| a | b |\n| --- | --- |\n| 1 | 2 |\n",
    "$$\nE = mc^2\n$$\n\n[[pagebreak]]\n",
)


@pytest.mark.parametrize("markdown", FEATURES)
def test_rendered_document_is_structurally_valid(tmp_path: Path, markdown: str) -> None:
    parts = _parts(tmp_path, markdown)
    assert validate_parts(parts) == []


def test_full_example_document_is_structurally_valid() -> None:
    """用真实示例（覆盖 W0~W3 全部特性）做校验。"""
    fixtures = Path(__file__).parent.parent / "examples" / "minimal"
    markdown = (fixtures / "content.md").read_text(encoding="utf-8")
    config = load_config(fixtures / "config.toml")
    data = render_docx_bytes(parse_dfm(markdown), config, base_dir=fixtures)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        parts = {name: archive.read(name) for name in archive.namelist()}
    assert validate_parts(parts) == []


def test_field_elements_are_wrapped_in_runs(tmp_path: Path) -> None:
    """回归：域元素（fldChar/instrText）必须在 run 内。"""
    parts = _parts(tmp_path, "\\begin{caption #fig:1}\n图题\n\\end{caption}\n")
    document = parts["word/document.xml"].decode("utf-8")
    assert "<w:r><w:fldChar" in document.replace("\n", "")
    assert "<w:r><w:instrText" in document.replace("\n", "")


def test_bookmarks_are_not_empty_and_ids_unique(tmp_path: Path) -> None:
    """回归：书签必须包住内容，且 id 不重复（否则 REF 域取不到/取错）。"""
    import re

    parts = _parts(
        tmp_path,
        "\\begin{caption #fig:1}\n图一\n\\end{caption}\n\n"
        "\\begin{equation #eq:1 number=1}\n$$x=1$$\n\\end{equation}\n",
    )
    document = parts["word/document.xml"].decode("utf-8")
    starts = re.findall(r'<w:bookmarkStart w:id="(\d+)" w:name="([^"]+)"/>', document)
    ends = re.findall(r'<w:bookmarkEnd w:id="(\d+)"/>', document)
    ids = [int(i) for i, _ in starts]
    assert len(starts) == len(ends) == 2
    assert len(set(ids)) == len(ids), f"书签 id 重复: {starts}"
    # 书签不能是紧挨着的空区间：start 与 end 之间必须有 run
    for match in re.finditer(r"<w:bookmarkStart [^>]*/>(.*?)<w:bookmarkEnd", document, re.DOTALL):
        assert "<w:r>" in match.group(1), "空书签：书签里没有任何内容"


def test_font_table_registers_used_fonts(tmp_path: Path) -> None:
    """字体必须登记进 fontTable，否则 Word/预览会提示缺少字体。"""
    parts = _parts(tmp_path, "```python\nprint(1)\n```\n")
    fonts = parts["word/fontTable.xml"].decode("utf-8")
    assert 'w:name="Consolas"' in fonts
    assert 'w:name="等线"' in fonts  # 代码块里中文的回退字体

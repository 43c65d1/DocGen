"""金标准交叉验证：IR 与 markdown-it token 流的一次性归约必须结构等价。

覆盖点都是历史上真出过问题的地方：嵌套列表、列表项里能否放多个块、引用嵌套、
围栏语言、表格行列、标题层级、有序/无序切换。
"""

from pathlib import Path

import pytest

from docgen.canonical import compare_document, ir_structure, iter_blocks, token_structure
from docgen.parser.dfm import parse_dfm

FIXTURES = Path(__file__).parent / "fixtures"


def _assert_matches(text: str) -> None:
    diffs = compare_document(text, parse_dfm(text))
    assert diffs == [], "\n".join(
        f"{d.reason} @#{d.index}: expected={d.expected!r} actual={d.actual!r}" for d in diffs
    )


# --------------------------------------------------------------------------
# 逐个块级语法
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "markdown",
    [
        "# 一级\n\n## 二级\n\n### 三级\n\n###### 六级\n",
        "普通段落。\n\n第二段。\n",
        "- 甲\n- 乙\n",
        "- 甲\n  - 乙\n    - 丙\n",
        "1. 一\n2. 二\n",
        "- 甲\n\n1. 一\n",
        "- 项一，含 **粗体** 与 `code`\n- 项二\n",
        "> 引用一段\n>\n> 引用二段\n",
        "> 外层\n>\n> > 内层\n",
        "```python\nprint(1)\n```\n",
        "```\n纯文本\n```\n",
        "---\n",
        "| 列 A | 列 B |\n| --- | --- |\n| a1 | b1 |\n| a2 | b2 |\n",
        "混合文档：\n\n# 标题\n\n- 甲\n  - 乙\n\n> 引用\n\n```py\nx = 1\n```\n\n---\n",
    ],
)
def test_document_matches_gold_standard(markdown: str) -> None:
    _assert_matches(markdown)


def test_full_fixture_matches_gold_standard() -> None:
    """真实夹具里含自定义标记：金标准侧把它们当文本，IR 侧归约时要剥掉标记。"""
    text = (FIXTURES / "full.md").read_text(encoding="utf-8")
    expected = token_structure(text)
    actual = ir_structure(parse_dfm(text))
    # 自定义标记在两边都被剥掉，所以完整文档也必须逐行一致
    assert actual == expected


# --------------------------------------------------------------------------
# 差异必须被报出来（避免比较器本身太宽松）
# --------------------------------------------------------------------------
def test_detects_wrong_heading_level() -> None:
    """人为构造不一致：IR 说 h2，金标准说 h1。"""
    from docgen.ir import Heading, Text

    fake = [Heading(level=2, content=[Text("标题")], source_line=1)]
    diffs = compare_document("# 标题\n", fake)
    assert diffs and diffs[0].kind == "h2"
    assert "h1" in diffs[0].expected


def test_detects_missing_nested_list() -> None:
    from docgen.ir import ListBlock, ListItem, Paragraph, Text

    flat = ListBlock(
        source_line=1,
        ordered=False,
        items=[
            ListItem(source_line=1, content=[Paragraph(content=[Text("父")], source_line=1)]),
            ListItem(source_line=2, content=[Paragraph(content=[Text("子")], source_line=2)]),
        ],
    )
    diffs = compare_document("- 父\n  - 子\n", [flat])
    assert any(d.reason in ("结构与金标准不一致", "元素数量不一致") for d in diffs)


def test_detects_wrong_language() -> None:
    from docgen.ir import CodeBlock

    diffs = compare_document(
        "```python\nx\n```\n", [CodeBlock(language="py", content="x\n", source_line=1)]
    )
    assert diffs and diffs[0].actual.startswith("pre[py]")


# --------------------------------------------------------------------------
# 工具函数
# --------------------------------------------------------------------------
def test_iter_blocks_flattens_nested_blocks() -> None:
    blocks = parse_dfm("> 引用\n\n- 项\n  - 嵌套\n")
    kinds = [type(block).__name__ for block in iter_blocks(blocks)]
    assert kinds.count("Paragraph") == 3  # 引用内 1 + 父项 1 + 嵌套项 1
    assert kinds.count("ListBlock") == 2
    assert "BlockQuote" in kinds and "ListItem" in kinds


def test_token_structure_uses_heading_tags() -> None:
    assert token_structure("## 标题\n") == ["h2 标题"]


def test_token_structure_normalizes_wiki_placeholders() -> None:
    """两边对 [[...]] 的占位统一（金标准=字面文本，产品=Image），所以比的是占位。"""
    text = "[[img:pics/a.png]]\n"
    assert token_structure(text) == ["<wiki>"]
    assert ir_structure(parse_dfm(text)) == ["<wiki>"]


def test_pagebreak_normalizes_on_both_sides() -> None:
    """独立成段的 [[pagebreak]] 两边都归约成 hr（产品侧是 PageBreak 节点）。"""
    text = "[[pagebreak]]\n"
    assert token_structure(text) == ["hr"]
    assert ir_structure(parse_dfm(text)) == ["hr"]


def test_empty_document_matches() -> None:
    assert compare_document("", parse_dfm("")) == []

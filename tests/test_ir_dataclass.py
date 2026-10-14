"""IR 不可变契约：全部节点 frozen、字段齐全、相等与哈希按值比较。"""

from dataclasses import FrozenInstanceError

import pytest

from docgen import ir


def _all_inline_nodes() -> list[object]:
    return [
        ir.Text(content="文本"),
        ir.Styled(content=[ir.Text("红色")], style_name="keyword"),
        ir.Code(content="x = 1"),
        ir.Math(latex="x^2"),
        ir.Math(latex="\\frac{1}{2}", display=True),
        ir.Link(url="https://example.com", content=[ir.Text("链接")]),
        ir.Image(src="pics/a.png", alt="图"),
        ir.Break(),
    ]


def _all_block_nodes() -> list[object]:
    return [
        ir.Heading(level=2, content=[ir.Text("标题")], source_line=1),
        ir.Paragraph(content=[ir.Text("段落")], source_line=3),
        ir.ListBlock(
            ordered=False,
            items=[
                ir.ListItem(
                    source_line=5,
                    content=[ir.Paragraph(content=[ir.Text("项")], source_line=5)],
                )
            ],
            source_line=5,
        ),
        ir.CodeBlock(language="python", content="print(1)\n", source_line=7),
        ir.Formula(latex="E = mc^2", source_line=9),
        ir.ImageBlock(src="pics/a.png", alt="图", source_line=11),
        ir.ThematicBreak(source_line=13),
        ir.BlockQuote(
            content=[ir.Paragraph(content=[ir.Text("引用")], source_line=15)],
            source_line=15,
        ),
        ir.Table(rows=[["a", "b"]], source_line=17),
    ]


def test_inline_nodes_are_inline_markers() -> None:
    assert all(isinstance(n, ir.Inline) for n in _all_inline_nodes())


def test_block_nodes_carry_source_line() -> None:
    for node in _all_block_nodes():
        assert isinstance(node, ir.Block)
        assert isinstance(node.source_line, int)
        assert node.source_line > 0


def test_equality_is_by_value() -> None:
    assert ir.Text(content="a") == ir.Text(content="a")
    assert ir.Text(content="a") != ir.Text(content="b")
    assert ir.Styled(content=[ir.Text("a")], style_name="k") == ir.Styled(
        content=[ir.Text("a")], style_name="k"
    )
    assert ir.Table(rows=[["a"]], source_line=1) == ir.Table(rows=[["a"]], source_line=1)
    assert ir.ThematicBreak(source_line=1) != ir.ThematicBreak(source_line=2)


def test_nodes_are_frozen() -> None:
    node = ir.Text(content="a")
    with pytest.raises(FrozenInstanceError):
        node.content = "b"  # type: ignore[misc]


def test_immutable_nodes_are_hashable() -> None:
    assert len({ir.Text(content="a"), ir.Text(content="a"), ir.Code(content="a")}) == 2
    assert hash(ir.Math(latex="x")) == hash(ir.Math(latex="x"))


def test_math_display_defaults_to_inline() -> None:
    assert ir.Math(latex="x").display is False
    assert ir.Formula(latex="x", source_line=1).display is True


def test_image_alt_defaults_to_empty() -> None:
    assert ir.Image(src="a.png").alt == ""
    assert ir.ImageBlock(src="a.png", source_line=1).alt == ""


def test_list_item_holds_blocks() -> None:
    item = ir.ListItem(
        source_line=1,
        content=[ir.Paragraph(content=[ir.Text("项")], source_line=1)],
    )
    assert isinstance(item.content[0], ir.Block)

"""IR -> HTML（手册 §4 / 第 4 周）。

渲染层只认 IR + config：

- 块级节点按 IR 类型分派，输出固定标签与顺序（确定性）。
- 行内样式（``Styled``）从 config 的样式表取**最终值**，写成内联 ``style``，
  保证「输出中的样式属性 == config 声明值」这条可测试不变量。
- 文本与属性一律 HTML 转义；样式名未在 config 中声明时只丢失样式，不丢内容。
"""

from __future__ import annotations

import html
from typing import Any, assert_never

from ..config import Config, build_style_table
from ..ir import (
    BlockNode,
    BlockQuote,
    Break,
    Code,
    CodeBlock,
    Footnote,
    Formula,
    Heading,
    Image,
    ImageBlock,
    InlineNode,
    Link,
    ListBlock,
    ListItem,
    Math,
    NamedBlock,
    PageBreak,
    Paragraph,
    Ref,
    Styled,
    Table,
    Text,
    ThematicBreak,
    Toc,
)
from .css import inline_style, render_css

__all__ = ["render_blocks", "render_html"]

_HEADINGS = {1: "h1", 2: "h2", 3: "h3", 4: "h4", 5: "h5", 6: "h6"}
_BUILTIN_TAGS = {"strong": "strong", "em": "em", "strike": "del"}


def render_html(
    blocks: list[BlockNode],
    config: Config,
    title: str = "",
    full_document: bool = True,
) -> str:
    """渲染块级 IR。

    ``full_document=True`` 返回完整 HTML 文档（含 ``<head>`` 与生成的 CSS），
    否则只返回 ``<body>`` 内部片段（便于测试与嵌入）。
    """
    style_table = build_style_table(config)
    body = render_blocks(blocks, style_table, heading=1)

    if not full_document:
        return body

    safe_title = html.escape(title or "DocGen")
    return (
        "<!DOCTYPE html>\n"
        '<html lang="zh">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        f"<title>{safe_title}</title>\n"
        "<style>\n"
        f"{render_css(config)}"
        "</style>\n"
        "</head>\n"
        "<body>\n"
        f"{body}"
        "</body>\n"
        "</html>\n"
    )


def render_blocks(
    blocks: list[BlockNode],
    style_table: dict[str, dict[str, Any]],
    heading: int = 2,
) -> str:
    """把一个块级节点列表渲染成 HTML 片段（每个块占一行）。"""
    lines: list[str] = []
    for block in blocks:
        lines.extend(_render_block(block, style_table, heading))
    return "".join(line + "\n" for line in lines)


def _render_block(
    block: BlockNode, style_table: dict[str, dict[str, Any]], heading: int
) -> list[str]:
    if isinstance(block, Heading):
        tag = _HEADINGS.get(block.level, f"h{heading}")
        style = _style_attr(style_table, f"heading{block.level}")
        return [f"<{tag}{style}>{_render_inline(block.content, style_table)}</{tag}>"]
    if isinstance(block, Paragraph):
        style = _style_attr(style_table, "body")
        return [f"<p{style}>{_render_inline(block.content, style_table)}</p>"]
    if isinstance(block, ListBlock):
        return _render_list(block, style_table, heading)
    if isinstance(block, CodeBlock):
        return _render_code_block(block, style_table)
    if isinstance(block, Formula):
        return [f'<div class="math display">{html.escape(block.latex.strip())}</div>']
    if isinstance(block, ImageBlock):
        return [_render_image(block.src, block.alt)]
    if isinstance(block, ThematicBreak):
        return ["<hr>"]
    if isinstance(block, PageBreak):
        return ['<hr class="pagebreak">']
    if isinstance(block, BlockQuote):
        lines = ["<blockquote>"]
        for child in block.content:
            lines.extend(_render_block(child, style_table, heading))
        lines.append("</blockquote>")
        return lines
    if isinstance(block, Table):
        return _render_table(block)
    if isinstance(block, NamedBlock):
        return _render_named_block(block, style_table, heading)
    if isinstance(block, Toc):
        return ['<nav class="toc">目录（构建 HTML 时由文档结构生成；Word 侧是 TOC 域）</nav>']
    assert_never(block)


def _render_named_block(
    block: NamedBlock, style_table: dict[str, dict[str, Any]], heading: int
) -> list[str]:
    """命名块：``<div class="名字">`` 包住内容；``id`` 来自 Pandoc 属性。"""
    classes = [block.name]
    extra = block.attributes.get("classes")
    if extra:
        classes.extend(extra.split())
    attributes = f' class="{" ".join(classes)}"'
    if block.attributes.get("id"):
        attributes += f' id="{html.escape(block.attributes["id"], quote=True)}"'
    lines = [f"<div{attributes}>"]
    inner = render_blocks(block.content, style_table, heading).rstrip("\n")
    if inner:
        lines.extend(inner.split("\n"))
    lines.append("</div>")
    return lines


def _render_list(
    block: ListBlock, style_table: dict[str, dict[str, Any]], heading: int
) -> list[str]:
    tag = "ol" if block.ordered else "ul"
    lines = [f"<{tag}>"]
    for item in block.items:
        lines.extend(_render_list_item(item, style_table, heading))
    lines.append(f"</{tag}>")
    return lines


def _render_list_item(
    item: ListItem, style_table: dict[str, dict[str, Any]], heading: int
) -> list[str]:
    """单个列表项：单段落列表项压成一行 ``<li>文本</li>``，其余保持块结构。"""
    if len(item.content) == 1 and isinstance(item.content[0], Paragraph):
        paragraph = item.content[0]
        return [f"<li>{_render_inline(paragraph.content, style_table)}</li>"]

    lines = ["<li>"]
    for child in item.content:
        lines.extend(_render_block(child, style_table, heading))
    lines.append("</li>")
    return lines


def _render_code_block(block: CodeBlock, style_table: dict[str, dict[str, Any]]) -> list[str]:
    properties = style_table.get("code_block", {})
    style = f' style="{inline_style(properties)}"' if properties else ""
    class_attr = f' class="language-{html.escape(block.language)}"' if block.language else ""
    return [f"<pre{style}><code{class_attr}>{html.escape(block.content)}</code></pre>"]


def _render_table(block: Table) -> list[str]:
    if not block.rows:
        return ["<table></table>"]
    head, *body = block.rows
    lines = ["<table>", "<thead>", "<tr>"]
    lines.extend(f"<th>{html.escape(cell)}</th>" for cell in head)
    lines.extend(["</tr>", "</thead>"])
    if body:
        lines.append("<tbody>")
        for row in body:
            lines.append("<tr>")
            lines.extend(f"<td>{html.escape(cell)}</td>" for cell in row)
            lines.append("</tr>")
        lines.append("</tbody>")
    lines.append("</table>")
    return lines


def _render_image(src: str, alt: str) -> str:
    return f'<img src="{html.escape(src, quote=True)}" alt="{html.escape(alt, quote=True)}">'


def _render_inline(nodes: list[InlineNode], style_table: dict[str, dict[str, Any]]) -> str:
    return "".join(_render_inline_node(node, style_table) for node in nodes)


def _render_inline_node(node: InlineNode, style_table: dict[str, dict[str, Any]]) -> str:
    if isinstance(node, Text):
        return html.escape(node.content)
    if isinstance(node, Code):
        return f"<code>{html.escape(node.content)}</code>"
    if isinstance(node, Break):
        return "<br>"
    if isinstance(node, Math):
        return f'<span class="math">{html.escape(node.latex)}</span>'
    if isinstance(node, Image):
        return _render_image(node.src, node.alt)
    if isinstance(node, Link):
        body = _render_inline(node.content, style_table)
        return f'<a href="{html.escape(node.url, quote=True)}">{body}</a>'
    if isinstance(node, Styled):
        body = _render_inline(node.content, style_table)
        return _render_styled(node.style_name, body, style_table)
    if isinstance(node, Ref):
        target = html.escape(node.target, quote=True)
        return f'<a class="xref" href="#{target}">[{html.escape(node.target)}]</a>'
    if isinstance(node, Footnote):
        return f'<sup class="footnote" title="{html.escape(node.text, quote=True)}">†</sup>'
    assert_never(node)


def _render_styled(style_name: str, body: str, style_table: dict[str, dict[str, Any]]) -> str:
    tag = _BUILTIN_TAGS.get(style_name)
    properties = style_table.get(style_name, {})
    if not properties and tag:
        return f"<{tag}>{body}</{tag}>"

    if not properties:
        # 样式未在 config 中声明：只丢样式，不丢内容
        return body

    style = f' style="{inline_style(properties)}"'
    if tag:
        return f"<{tag}{style}>{body}</{tag}>"
    return f"<span{style}>{body}</span>"


def _style_attr(style_table: dict[str, dict[str, Any]], style_name: str) -> str:
    properties = style_table.get(style_name)
    if not properties:
        return ""
    return f' style="{inline_style(properties)}"'

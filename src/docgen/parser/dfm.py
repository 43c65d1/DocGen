"""DFM -> IR 解析器（手册 5.1 / 第 1、3 周）。

实现要点：

- 块级结构交给 markdown-it-py（标题、段落、列表、引用、代码块、分隔线、表格），
  DFM 自研标记由 :mod:`docgen.parser.rules` 注册的行内规则负责。
- 每个块级节点都带 ``source_line``（1 起，指向源文件行号）。
- 渲染层只认 IR：本模块不产生任何 HTML。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from markdown_it import MarkdownIt

from ..ir import (
    BlockNode,
    BlockQuote,
    Break,
    Code,
    CodeBlock,
    DiagonalHeader,
    Footnote,
    Formula,
    Heading,
    Image,
    ImageBlock,
    Link,
    ListBlock,
    ListItem,
    Math,
    PageBreak,
    Paragraph,
    Ref,
    SectionBreak,
    Styled,
    Table,
    Text,
    ThematicBreak,
    Toc,
)
from .begin_block import BEGIN_PLACEHOLDER, BeginBlock, extract_begin_blocks, parse_begin_block
from .rules import register_rules

if TYPE_CHECKING:  # pragma: no cover
    from markdown_it.token import Token

    from ..ir import InlineNode


_EMPHASIS_OPEN = {"strong_open": "strong", "em_open": "em", "s_open": "strike"}
_EMPHASIS_CLOSE = ("strong_close", "em_close", "s_close")
_LIST_OPEN = ("bullet_list_open", "ordered_list_open")
_LIST_CLOSE = ("bullet_list_close", "ordered_list_close")

__all__ = ["parse_dfm"]


def parse_dfm(text: str) -> list[BlockNode]:
    """把 DFM 源文本解析成块级 IR 列表。

    先抽出 ``\\begin{...}`` 块（手册 §6.2.5 的双语法），再把剩余文本交给
    markdown-it；``\\begin`` 区域被替换成同形占位行，所以行号与源文件一致。
    """
    prepared, begin_blocks = extract_begin_blocks(text)
    md = MarkdownIt("commonmark").enable("table").enable("strikethrough")
    register_rules(md)
    tokens = md.parse(prepared)
    return _blocks_in_range(tokens, 0, len(tokens), begin_blocks)


# --------------------------------------------------------------------------
# 行内
# --------------------------------------------------------------------------
def _inline_to_ir(tokens: list[Token]) -> list[InlineNode]:
    """把 inline token 的 children 转成 IR 行内节点。

    粗体 / 斜体 / 删除线在 IR 层统一表达为 ``Styled``（样式名 strong / em / strike），
    具体视觉由 config 的样式表决定。
    """
    result: list[InlineNode] = []
    stack: list[list[InlineNode]] = [result]

    for tok in tokens:
        if tok.type == "text":
            if tok.content:
                stack[-1].append(Text(tok.content))
        elif tok.type == "code_inline":
            stack[-1].append(Code(tok.content))
        elif tok.type == "softbreak":
            stack[-1].append(Text(" "))
        elif tok.type == "hardbreak":
            stack[-1].append(Break())
        elif tok.type in _EMPHASIS_OPEN:
            node: list[InlineNode] = []
            stack[-1].append(Styled(content=node, style_name=_EMPHASIS_OPEN[tok.type]))
            stack.append(node)
        elif tok.type in _EMPHASIS_CLOSE:
            if len(stack) > 1:
                stack.pop()
        elif tok.type == "link_open":
            node = []
            stack[-1].append(Link(url=_attr(tok, "href"), content=node))
            stack.append(node)
        elif tok.type == "link_close":
            if len(stack) > 1:
                stack.pop()
        elif tok.type == "image":
            stack[-1].append(Image(src=_attr(tok, "src"), alt=tok.content))
        elif tok.type == "dfm_image":
            # ``[[img:path width=2cm]]``：第一段是路径，其余是属性
            target = tok.content.split()
            stack[-1].append(Image(src=target[0] if target else "", alt=""))
        elif tok.type == "dfm_pagebreak":
            stack[-1].append(Break())
        elif tok.type == "dfm_toc":
            stack[-1].append(Ref(target="__toc__"))  # 段落内的 [[toc]] 按引用占位处理
        elif tok.type == "dfm_sectionbreak":
            # 段落内的分节符没有意义（分节是块级动作），当作硬换行占位
            stack[-1].append(Break())
        elif tok.type == "dfm_diag":
            # 用 ; 分隔（不能用 |：那是 GFM 表格的单元格分隔符，会把表格拆坏）
            upper, _, lower = tok.content.partition(";")
            stack[-1].append(DiagonalHeader(upper=upper.strip(), lower=lower.strip()))
        elif tok.type == "dfm_ref":
            stack[-1].append(Ref(target=tok.content))
        elif tok.type == "dfm_footnote":
            stack[-1].append(Footnote(text=tok.content))
        elif tok.type == "dfm_math":
            stack[-1].append(Math(latex=tok.content, display=_is_display(tok)))
        elif tok.type == "dfm_script":
            script = str((tok.meta or {}).get("script", "sup"))
            stack[-1].append(Styled(content=[Text(tok.content)], style_name=script))
        elif tok.type == "dfm_styled_open":
            node = []
            stack[-1].append(Styled(content=node, style_name=_attr(tok, "style")))
            stack.append(node)
        elif tok.type == "dfm_styled_close" and len(stack) > 1:
            stack.pop()

    return result


def _attr(token: Token, name: str) -> str:
    """markdown-it 的属性值可能是 str / int / float，IR 只接受 str。"""
    value = token.attrGet(name)
    return "" if value is None else str(value)


def _is_display(token: Token) -> bool:
    return bool((token.meta or {}).get("display", False))


def _is_pagebreak_only(tokens: list[Token]) -> bool:
    """整段只有一个 ``[[pagebreak]]`` 标记：升级为块级分页。"""
    if not any(t.type == "dfm_pagebreak" for t in tokens):
        return False
    return all(t.type == "dfm_pagebreak" for t in tokens)


def _sole_token_type(tokens: list[Token]) -> str | None:
    """整段只有一个标记 token 时返回它的类型（用于升级成块级节点）。"""
    return tokens[0].type if len(tokens) == 1 else None


def _block_math(tokens: list[Token]) -> str | None:
    """整段是 ``$$ ... $$`` 时返回 LaTeX 源文本，否则返回 None。"""
    if len(tokens) < 2:
        return None
    if tokens[0].type != "text" or tokens[0].content.strip() != "$$":
        return None
    if tokens[-1].type != "text" or tokens[-1].content.strip() != "$$":
        return None

    pieces: list[str] = []
    for tok in tokens[1:-1]:
        if tok.type == "text":
            pieces.append(tok.content)
        elif tok.type in ("softbreak", "hardbreak"):
            pieces.append("\n")
        else:
            return None
    return "".join(pieces).strip()


# --------------------------------------------------------------------------
# 块级
# --------------------------------------------------------------------------
def _line_of(token: Token, fallback: int = 0) -> int:
    return token.map[0] + 1 if token.map else fallback


def _placeholder_index(inline_token: Token | None) -> int | None:
    """识别预扫描留下的 ``\\begin`` 占位段落，返回块下标。"""
    if inline_token is None:
        return None
    children = inline_token.children or []
    if len(children) != 1 or children[0].type != "text":
        return None
    content = children[0].content.strip()
    if not content.startswith(BEGIN_PLACEHOLDER):
        return None
    digits = content[len(BEGIN_PLACEHOLDER) :]
    return int(digits) if digits.isdigit() else None


def _blocks_in_range(
    tokens: list[Token],
    start: int,
    end: int,
    begin_blocks: list[BeginBlock] | None = None,
) -> list[BlockNode]:
    """把 ``tokens[start:end]`` 里的顶层块级 token 转成 IR。"""
    blocks: list[BlockNode] = []
    i = start
    while i < end:
        token = tokens[i]
        if token.type == "heading_open":
            blocks.append(
                Heading(
                    level=int(token.tag[1]),
                    content=_inline_to_ir(tokens[i + 1].children or []),
                    source_line=_line_of(token),
                )
            )
            i += 3
        elif token.type == "paragraph_open":
            placeholder = _placeholder_index(tokens[i + 1])
            if placeholder is not None and begin_blocks is not None:
                blocks.append(parse_begin_block(begin_blocks[placeholder]))
            else:
                blocks.append(_paragraph_block(token, tokens[i + 1]))
            i += 3
        elif token.type in _LIST_OPEN:
            listed, i = _list_block(tokens, i, end)
            blocks.append(listed)
        elif token.type == "blockquote_open":
            quoted, i = _blockquote(tokens, i, end)
            blocks.append(quoted)
        elif token.type == "fence":
            blocks.append(
                CodeBlock(
                    language=token.info.strip(),
                    content=token.content,
                    source_line=_line_of(token),
                )
            )
            i += 1
        elif token.type == "hr":
            blocks.append(ThematicBreak(source_line=_line_of(token)))
            i += 1
        elif token.type == "table_open":
            table, i = _table(tokens, i, end)
            blocks.append(table)
        else:
            i += 1
    return blocks


def _paragraph_block(open_token: Token, inline_token: Token | None) -> BlockNode:
    children = _meaningful_children(inline_token)
    source_line = _line_of(open_token)

    latex = _block_math(children)
    if latex is not None:
        return Formula(latex=latex, source_line=source_line)
    if len(children) == 1 and children[0].type == "dfm_math" and _is_display(children[0]):
        return Formula(latex=children[0].content, source_line=source_line)
    if len(children) == 1 and children[0].type == "dfm_pagebreak":
        return PageBreak(source_line=source_line)
    if len(children) == 1 and children[0].type == "dfm_sectionbreak":
        return SectionBreak(source_line=source_line)
    if len(children) == 1 and children[0].type == "dfm_toc":
        return Toc(source_line=source_line)

    content = _inline_to_ir(children)
    if len(content) == 1 and isinstance(content[0], Image):
        image = content[0]
        return ImageBlock(
            src=image.src,
            alt=image.alt,
            width=_image_attribute(children, "width"),
            align=_image_attribute(children, "align"),
            source_line=source_line,
        )
    return Paragraph(content=content, source_line=source_line)


def _image_attribute(tokens: list[Token], name: str) -> str:
    """从 ``[[img:path width=2cm]]`` 这样的标记里取属性（值写在 token.content 里）。"""
    for tok in tokens:
        if tok.type != "dfm_image":
            continue
        for part in tok.content.split()[1:]:
            key, _, value = part.partition("=")
            if key.strip() == name:
                return value.strip()
    return ""


def _meaningful_children(inline_token: Token | None) -> list[Token]:
    """去掉空 text token：自研规则用 pushPending 时会留下空片段。"""
    if inline_token is None:
        return []
    return [
        tok
        for tok in (inline_token.children or [])
        if not (tok.type == "text" and tok.content == "")
    ]


def _list_block(tokens: list[Token], start: int, end: int) -> tuple[ListBlock, int]:
    open_token = tokens[start]
    ordered = open_token.type == "ordered_list_open"
    items: list[ListItem] = []
    depth = 0
    i = start

    while i < end:
        token = tokens[i]
        if token.type in _LIST_OPEN:
            depth += 1
            if depth > 1:
                i = _skip_container(tokens, i, end, _LIST_OPEN, _LIST_CLOSE)
                continue
        elif token.type in _LIST_CLOSE:
            depth -= 1
            if depth == 0:
                return (
                    ListBlock(ordered=ordered, items=items, source_line=_line_of(open_token)),
                    i + 1,
                )
        elif token.type == "list_item_open" and depth == 1:
            item, i = _list_item(tokens, i, end)
            items.append(item)
            continue
        i += 1

    return ListBlock(ordered=ordered, items=items, source_line=_line_of(open_token)), i


def _list_item(tokens: list[Token], start: int, end: int) -> tuple[ListItem, int]:
    open_token = tokens[start]
    content: list[BlockNode] = []
    depth = 0
    i = start + 1

    while i < end:
        token = tokens[i]
        if token.type == "paragraph_open":
            content.append(_paragraph_block(token, tokens[i + 1] if i + 1 < end else None))
            i += 3
            continue
        if token.type == "heading_open":
            content.append(
                Heading(
                    level=int(token.tag[1]),
                    content=_inline_to_ir(tokens[i + 1].children or []),
                    source_line=_line_of(token),
                )
            )
            i += 3
            continue
        if token.type == "fence":
            content.append(
                CodeBlock(
                    language=token.info.strip(),
                    content=token.content,
                    source_line=_line_of(token),
                )
            )
            i += 1
            continue
        if token.type == "hr":
            content.append(ThematicBreak(source_line=_line_of(token)))
            i += 1
            continue
        if token.type == "blockquote_open":
            nested_quote, i = _blockquote(tokens, i, end)
            content.append(nested_quote)
            continue
        if token.type in _LIST_OPEN:
            depth += 1
            if depth == 1:
                nested, i = _list_block(tokens, i, end)
                content.append(nested)
                depth -= 1
                continue
        elif token.type in _LIST_CLOSE:
            depth -= 1
        elif token.type == "list_item_close" and depth == 0:
            return ListItem(content=content, source_line=_line_of(open_token)), i + 1
        i += 1

    return ListItem(content=content, source_line=_line_of(open_token)), i


def _blockquote(tokens: list[Token], start: int, end: int) -> tuple[BlockQuote, int]:
    open_token = tokens[start]
    depth = 0
    i = start

    while i < end:
        token = tokens[i]
        if token.type == "blockquote_open":
            depth += 1
            if depth == 1:
                inner_start = i + 1
        elif token.type == "blockquote_close":
            depth -= 1
            if depth == 0:
                return (
                    BlockQuote(
                        content=_blocks_in_range(tokens, inner_start, i),
                        source_line=_line_of(open_token),
                    ),
                    i + 1,
                )
        i += 1

    return BlockQuote(content=[], source_line=_line_of(open_token)), i


def _table(tokens: list[Token], start: int, end: int) -> tuple[Table, int]:
    open_token = tokens[start]
    rows: list[list[str]] = []
    row: list[str] = []
    cell_nodes: list[list[list[InlineNode]]] = []
    nodes_row: list[list[InlineNode]] = []
    row_alignments: list[str] = []
    alignments: list[str] = []
    i = start

    while i < end:
        token = tokens[i]
        if token.type == "table_close":
            return (
                Table(
                    rows=rows,
                    source_line=_line_of(open_token),
                    alignments=alignments,
                    cell_nodes=cell_nodes,
                ),
                i + 1,
            )
        if token.type == "tr_open":
            row = []
            nodes_row = []
            row_alignments = []
        elif token.type == "tr_close":
            rows.append(row)
            cell_nodes.append(nodes_row)
            if not alignments and any(row_alignments):
                alignments = list(row_alignments)
        elif token.type in ("th_open", "td_open"):
            inline = tokens[i + 1] if i + 1 < end else None
            row.append(_cell_text(inline))
            # 同时保留行内 IR：单元格里的粗体/代码/公式不能被拍平
            nodes_row.append(_inline_to_ir(inline.children or []) if inline else [])
            if token.type == "th_open":
                row_alignments.append(_alignment_of(_attr(token, "style")))
        i += 1

    return (
        Table(
            rows=rows,
            source_line=_line_of(open_token),
            alignments=alignments,
            cell_nodes=cell_nodes,
        ),
        i,
    )


def _alignment_of(css_style: str) -> str:
    """``text-align:center`` -> ``center``（GFM 分隔行的对齐标记）。"""
    for part in css_style.split(";"):
        if ":" not in part:
            continue
        key, _, value = part.partition(":")
        if key.strip() == "text-align":
            return value.strip()
    return ""


def _cell_text(inline: Token | None) -> str:
    """表格单元格统一按纯文本处理（剪枝版不支持单元格内样式）。"""
    if inline is None or not inline.children:
        return ""
    pieces: list[str] = []
    for tok in inline.children:
        if tok.type in ("text", "code_inline"):
            pieces.append(tok.content)
        elif tok.type in ("softbreak", "hardbreak"):
            pieces.append(" ")
        elif tok.type == "dfm_math":
            pieces.append(f"${tok.content}$")
        elif tok.type == "dfm_pagebreak":
            pieces.append("[[pagebreak]]")
        elif tok.type == "dfm_sectionbreak":
            pieces.append("[[sectionbreak]]")
        elif tok.type == "dfm_diag":
            pieces.append(f"[[diag:{tok.content}]]")
        elif tok.type == "dfm_image":
            pieces.append(f"[[img:{tok.content}]]")
    return "".join(pieces)


def _skip_container(
    tokens: list[Token],
    start: int,
    end: int,
    open_types: tuple[str, ...],
    close_types: tuple[str, ...],
) -> int:
    """跳过一个嵌套容器（列表等），返回它之后的下标。"""
    depth = 0
    i = start
    while i < end:
        if tokens[i].type in open_types:
            depth += 1
        elif tokens[i].type in close_types:
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return i

"""金标准交叉验证（第 3 周）：用 markdown-it 的 token 流直接归约出「期望结构」。

我们的 IR 是**两遍**得到的：``md.parse`` 出 token，再由 ``parser/dfm.py`` 扫描成 IR。
两遍扫描正是历史 bug 的来源（嵌套列表被吞、列表项内容丢失）。所以这里用**一遍**：
同一个 token 流递归归约成规范结构，再与 IR 归约出的规范结构做结构等价比较。

比较维度（两边都必须一致）：

- 块级：``h<level>`` / ``p`` / ``ul``、``ol`` / ``li`` / ``blockquote`` / ``pre[lang]`` /
  ``hr`` / ``table``；嵌套结构按缩进体现
- 内容：元素内部的纯文本（行内标记剥掉后再比），空白折叠

跳过内部标记：``$$`` 块级公式两边的文本都是 ``$$``，会被跳过。

错误不用异常表达：返回带 ``reason`` 的差异列表，便于 pytest 逐条断言。
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, fields, is_dataclass
from typing import Any

from markdown_it import MarkdownIt
from markdown_it.token import Token

from .ir import Block, BlockQuote, CodeBlock, Heading, ListBlock, ListItem, Table
from .parser.rules import register_rules

__all__ = [
    "BlockDiff",
    "compare_document",
    "ir_structure",
    "normalize_markers",
    "token_structure",
]

_WIKI_IMAGE = re.compile(r"\[\[img:([^\]]*)\]\]")
_WIKI_ANY = re.compile(r"\[\[[^\]]*\]\]")
_STYLED = re.compile(r"\[([^\]]*)\]\{[^}]*\}")

#: 需要在比较前从两个结构里都去掉的元素（内部细节不同但合法性相同）
SKIP_MARKERS = ("<math>", "<math-display>")


@dataclass(frozen=True)
class BlockDiff:
    index: int
    kind: str
    reason: str
    expected: str = ""
    actual: str = ""


def _gold_md() -> MarkdownIt:
    """金标准解析器：与产品解析器同一 preset，但只注册数学标记。

    两个细节：

    - 数学规则必须注册在 ``text`` 之前，否则 ``$$`` 先被 text 规则切碎；
    - markdown-it 的 text 规则有一条「无特殊字符就跳过全部规则」的快速路径，
      ``$`` 不在默认 ``specialChars`` 里，所以要显式加上，规则才会被调用。
    """
    from .parser.rules import rule_math

    md = MarkdownIt("commonmark").enable("table").enable("strikethrough")
    md.inline.ruler.before("text", "dfm_math", rule_math)
    _add_special_chars(md, "$[")
    return md


def _add_special_chars(md: MarkdownIt, chars: str) -> None:
    """把字符加进 text 规则的 specialChars：否则快速路径会直接当成纯文本。"""
    for rule in md.inline.ruler2.getRules(""):
        if getattr(rule, "name", "") == "text":
            current = getattr(rule, "specialChars", "")
            rule.specialChars = "".join(dict.fromkeys(current + chars))  # type: ignore[attr-defined]


def _product_md() -> MarkdownIt:
    md = MarkdownIt("commonmark").enable("table").enable("strikethrough")
    register_rules(md)
    return md


def token_structure(text: str) -> list[str]:
    """把 markdown-it 的 token 流直接归约成规范结构（一遍扫描，无中间 IR）。"""
    tokens = _gold_md().parse(text)
    lines: list[str] = []
    _walk_tokens(tokens, 0, len(tokens), 0, lines)
    return normalize_markers(_clean(lines))


def ir_structure(blocks: Sequence[Block]) -> list[str]:
    """把 IR 归约成同一个规范结构。"""
    lines: list[str] = []
    for block in blocks:
        _describe_block(block, 0, lines)
    return normalize_markers(_clean(lines))


def normalize_markers(lines: list[str]) -> list[str]:
    """最终归约：字体标记占位与 ``[[img:]]`` 在两边统一成同一形式。"""
    return [re.sub(r"<wiki>|<image>", "<wiki>", line) for line in lines]


def compare_document(text: str, blocks: Sequence[Block]) -> list[BlockDiff]:
    """比较「token 流金标准」与「IR」：返回逐条差异（空列表表示完全一致）。"""
    expected = token_structure(text)
    actual = ir_structure(blocks)
    diffs: list[BlockDiff] = []
    for index, (want, got) in enumerate(zip(expected, actual)):
        if want != got:
            diffs.append(
                BlockDiff(
                    index=index,
                    kind=_kind_of(got),
                    reason="结构与金标准不一致",
                    expected=want,
                    actual=got,
                )
            )
    if len(expected) != len(actual):
        diffs.append(
            BlockDiff(
                index=min(len(expected), len(actual)),
                kind="document",
                reason="元素数量不一致",
                expected=str(len(expected)),
                actual=str(len(actual)),
            )
        )
    return diffs


# --------------------------------------------------------------------------
# token 流 -> 规范结构
# --------------------------------------------------------------------------
_CONTAINER_OPEN = {
    "bullet_list_open": "ul",
    "ordered_list_open": "ol",
    "blockquote_open": "blockquote",
}

_CONTAINER_CLOSE = {
    "bullet_list_close": "ul",
    "ordered_list_close": "ol",
    "blockquote_close": "blockquote",
}


def _walk_tokens(tokens: list[Token], start: int, end: int, depth: int, lines: list[str]) -> None:
    index = start
    while index < end:
        token = tokens[index]
        if token.type in _CONTAINER_OPEN:
            lines.append(_indent(depth) + _CONTAINER_OPEN[token.type])
            inner_end = _matching_close(tokens, index, end, token.type)
            _walk_tokens(tokens, index + 1, inner_end, depth + 1, lines)
            index = inner_end + 1
            continue
        if token.type in _CONTAINER_CLOSE:
            index += 1
            continue
        if token.type == "list_item_open":
            lines.append(_indent(depth) + "li")
            item_end = _matching_close(tokens, index, end, token.type)
            _walk_tokens(tokens, index + 1, item_end, depth + 1, lines)
            index = item_end + 1
            continue
        if token.type == "list_item_close":
            index += 1
            continue
        if token.type == "heading_open":
            inline = tokens[index + 1] if index + 1 < end else None
            lines.append(_indent(depth) + f"{token.tag} {_inline_text(inline)}")
            index += 3
            continue
        if token.type == "paragraph_open":
            inline = tokens[index + 1] if index + 1 < end else None
            body = _inline_text(inline)
            # 独立成段的图片/分页/公式：产品侧是 ImageBlock / PageBreak / Formula
            if body.startswith(("<image>", "<math-display>")):
                lines.append(_indent(depth) + body)
            elif body == "hr":
                lines.append(_indent(depth) + "hr")
            else:
                lines.append(_indent(depth) + f"p {body}")
            index += 3
            continue
        if token.type == "fence":
            language = token.info.strip().split()[0] if token.info.strip() else ""
            lines.append(_indent(depth) + f"pre[{language}] {token.content.strip()}")
            index += 1
            continue
        if token.type == "code_block":
            lines.append(_indent(depth) + f"pre[] {token.content.strip()}")
            index += 1
            continue
        if token.type == "hr":
            lines.append(_indent(depth) + "hr")
            index += 1
            continue
        if token.type in ("table_open", "thead_open", "tbody_open", "tr_open"):
            if token.type == "table_open":
                lines.append(_indent(depth) + "table")
                table_end = _matching_close(tokens, index, end, token.type)
                _walk_tokens(tokens, index + 1, table_end, depth + 1, lines)
                index = table_end + 1
                continue
            if token.type == "tr_open":
                row_end = _matching_close(tokens, index, end, token.type)
                cells: list[str] = []
                position = index + 1
                while position < row_end:
                    if tokens[position].type in ("th_open", "td_open"):
                        inline = tokens[position + 1] if position + 1 < row_end else None
                        cells.append(_inline_text(inline))
                        position += 3
                        continue
                    position += 1
                lines.append(_indent(depth) + "tr " + " | ".join(cells))
                index = row_end + 1
                continue
        index += 1


def _matching_close(tokens: list[Token], start: int, end: int, open_type: str) -> int:
    """找到与 ``open_type`` 配对的 close 下标（同类容器正确嵌套）。"""
    close_type = open_type.replace("_open", "_close")
    depth = 0
    index = start
    while index < end:
        if tokens[index].type == open_type:
            depth += 1
        elif tokens[index].type == close_type:
            depth -= 1
            if depth == 0:
                return index
        index += 1
    return end


def _inline_text(token: Token | None) -> str:
    if token is None:
        return ""
    return _inline_tokens_text(token.children or [])


def _inline_tokens_text(tokens: list[Token]) -> str:
    pieces: list[str] = []
    for token in tokens:
        if token.type in ("text", "code_inline"):
            pieces.append(token.content)
        elif token.type in ("softbreak", "hardbreak"):
            pieces.append(" ")
        elif token.type == "dfm_math":
            if (token.meta or {}).get("display"):
                return "<math-display>"  # 整段就是块级公式
            pieces.append(token.content)
        elif token.type == "image":
            pieces.append(token.content or "")
        elif token.children:
            pieces.append(_inline_tokens_text(token.children))
    # 标记归一必须在「整段拼好之后」做：markdown-it 可能把 [[ 与 ]] 切成多个 text token
    return _collapse(_normalize_text_markers("".join(pieces)))


def _normalize_text_markers(text: str) -> str:
    """金标准眼里的自定义标记是字面文本；归约时换成与 IR 侧一致的占位。"""
    if text.strip() == "[[pagebreak]]":
        return "hr"
    text = _WIKI_IMAGE.sub("<image>", text)
    text = _WIKI_ANY.sub("<wiki>", text)
    return _STYLED.sub(lambda m: m.group(1), text)


# --------------------------------------------------------------------------
# IR -> 规范结构
# --------------------------------------------------------------------------
def _describe_block(block: Block, depth: int, lines: list[str]) -> None:
    if isinstance(block, Heading):
        lines.append(_indent(depth) + f"h{block.level} {_inline_ir_text(block.content)}")
    elif isinstance(block, ListBlock):
        lines.append(_indent(depth) + ("ol" if block.ordered else "ul"))
        for item in block.items:
            _describe_item(item, depth + 1, lines)
    elif isinstance(block, BlockQuote):
        lines.append(_indent(depth) + "blockquote")
        for child in block.content:
            _describe_block(child, depth + 1, lines)
    elif isinstance(block, CodeBlock):
        lines.append(_indent(depth) + f"pre[{block.language}] {block.content.strip()}")
    elif isinstance(block, Table):
        lines.append(_indent(depth) + "table")
        for row in block.rows:
            lines.append(_indent(depth + 1) + "tr " + " | ".join(row))
    elif type(block).__name__ in ("ThematicBreak", "PageBreak"):
        lines.append(_indent(depth) + "hr")
    elif type(block).__name__ == "Formula":
        lines.append(_indent(depth) + "<math-display>")
    elif type(block).__name__ == "ImageBlock":
        lines.append(_indent(depth) + "<image>")
    elif type(block).__name__ in ("Paragraph", "ListItem"):
        content = getattr(block, "content", [])
        if content and isinstance(content[0], Block):
            for child in content:
                _describe_block(child, depth, lines)
        else:
            lines.append(_indent(depth) + f"p {_inline_ir_text(content)}")


def _describe_item(item: ListItem, depth: int, lines: list[str]) -> None:
    lines.append(_indent(depth) + "li")
    for child in item.content:
        _describe_block(child, depth + 1, lines)


def _inline_ir_text(nodes: Any) -> str:
    pieces: list[str] = []
    for node in _iter_inline_nodes(nodes):
        kind = type(node).__name__
        if kind == "Math":
            pieces.append(node.latex)
        elif kind == "Break":
            pieces.append(" ")
        elif kind == "Image":
            # 产品侧把独立成段的图片升级为 ImageBlock；行内图片与金标准同为字面文本
            pieces.append(node.alt or f"[[img:{node.src}]]")
        elif kind == "PageBreak":
            pieces.append("hr")
        elif isinstance(getattr(node, "content", None), str):
            pieces.append(node.content)
    return _collapse("".join(pieces))


def _iter_inline_nodes(nodes: Any) -> list[Any]:
    flat: list[Any] = []
    for node in nodes:
        flat.append(node)
        content = getattr(node, "content", None)
        if isinstance(content, list):
            flat.extend(_iter_inline_nodes(content))
    return flat


def _indent(depth: int) -> str:
    return "  " * depth


def _collapse(text: str) -> str:
    return " ".join(text.split())


def _kind_of(line: str) -> str:
    stripped = line.strip()
    return stripped.split(" ", 1)[0] if stripped else "document"


def _clean(lines: list[str]) -> list[str]:
    """丢弃空行（占位行保留，它们代表真实节点）。"""
    return [line for line in lines if line.strip()]


def iter_blocks(blocks: Sequence[Block]) -> list[Block]:
    """深度优先展平所有块级节点（含引用内、列表项内的嵌套块）。"""
    flat: list[Block] = []
    for block in blocks:
        flat.append(block)
        flat.extend(_nested_blocks(block))
    return flat


def _nested_blocks(block: Block) -> list[Block]:
    nested: list[Block] = []
    for value in _iter_values(block):
        if isinstance(value, Block):
            nested.append(value)
            nested.extend(_nested_blocks(value))
    return nested


def _iter_values(value: Any) -> list[Any]:
    """递归取出 dataclass 字段里的所有值（跳过本节点自身）。"""
    found: list[Any] = []
    if is_dataclass(value) and not isinstance(value, type):
        for field in fields(value):
            found.extend(_expand(getattr(value, field.name)))
    return found


def _expand(value: Any) -> list[Any]:
    if isinstance(value, list | tuple):
        return [item for item in value]
    return [value]

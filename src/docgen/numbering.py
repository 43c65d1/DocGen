"""编号 / 题注 / 交叉引用（完整版手册 W3）。

职责：

- **编号映射显式化**：``heading level -> (ilvl, style key)``，不再散落在渲染代码里
- **标签收集**：``\\begin{caption #fig:1}`` / ``\\begin{table #tab:1}`` /
  ``\\begin{equation #eq:1}`` 里的 ``#id`` 是引用目标
- **题注计数**：按类型（图/表/公式）各自从 1 开始
- **交叉引用校验**：``[[ref:...]]`` 指向不存在的目标 → ``E5004``；标签重复 → ``E4001``

域（Field）本身在渲染层生成：``SEQ`` 给题注编号、``REF`` 给交叉引用。
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import Config
from .errors import E_SYNTAX, E_UNKNOWN_REF
from .ir import BlockNode, BlockQuote, InlineNode, ListBlock, NamedBlock, Ref
from .validate import ContentError

__all__ = [
    "CAPTION_KINDS",
    "CaptionRef",
    "RefUse",
    "baked_fields",
    "caption_counters",
    "caption_kind",
    "collect_labels",
    "collect_refs",
    "heading_numbering",
    "validate_numbering",
]

#: 题注类型 -> 中文前缀（题注文本与 SEQ 域都用它）
CAPTION_KINDS: dict[str, str] = {
    "figure": "图",
    "table": "表",
    "equation": "公式",
}

#: 命名块名字 -> 题注类型（``caption`` 需要看属性里的 ``kind``，默认图）
_NAME_TO_KIND: dict[str, str] = {
    "figure": "figure",
    "table": "table",
    "equation": "equation",
}


@dataclass(frozen=True)
class CaptionRef:
    """一个题注（带标签）。"""

    label: str
    kind: str
    source_line: int
    text: str = ""


@dataclass(frozen=True)
class RefUse:
    """一处交叉引用。"""

    target: str
    source_line: int


def heading_numbering() -> dict[int, tuple[int, str]]:
    """标题层级 -> ``(ilvl, style key)``。

    母版里的多级编号是 ``numId=100``：``Heading1`` 绑 ``ilvl=0``、``Heading2`` 绑 ``ilvl=1``……
    这里把映射显式写出来（手册 W3 要求），渲染与校验都引用它。
    """
    return {level: (level - 1, f"Heading{level}") for level in range(1, 10)}


def caption_kind(block: NamedBlock) -> str:
    """命名块 -> 题注类型：``caption`` 看 ``kind`` 属性，其余按名字。"""
    if block.name == "caption":
        declared = block.attributes.get("kind", "")
        return declared if declared in CAPTION_KINDS else "figure"
    return _NAME_TO_KIND.get(block.name, block.name)


def iter_blocks(blocks: list[BlockNode]) -> list[BlockNode]:
    """深度优先展平所有块级节点（含引用内、列表项内、命名块内）。"""
    flat: list[BlockNode] = []
    for block in blocks:
        flat.append(block)
        if isinstance(block, BlockQuote):
            flat.extend(iter_blocks(block.content))
        elif isinstance(block, ListBlock):
            for item in block.items:
                flat.extend(iter_blocks(item.content))
        elif isinstance(block, NamedBlock):
            flat.extend(iter_blocks(block.content))
    return flat


def collect_labels(blocks: list[BlockNode]) -> dict[str, str]:
    """收集所有带 ``#id`` 的命名块：``{label: kind}``。"""
    labels: dict[str, str] = {}
    for block in iter_blocks(blocks):
        if isinstance(block, NamedBlock) and block.label:
            labels[block.label] = caption_kind(block)
    return labels


def collect_refs(blocks: list[BlockNode]) -> list[RefUse]:
    """收集全部 ``[[ref:...]]``，行号取所在块的行号。"""
    found: list[RefUse] = []
    for block in iter_blocks(blocks):
        line = block.source_line
        for node in _inline_nodes(block):
            if isinstance(node, Ref) and node.target != "__toc__":
                found.append(RefUse(target=node.target, source_line=line))
    return found


def _inline_nodes(block: BlockNode) -> list[InlineNode]:
    """取块级节点里的行内节点（标题/段落的 ``content``；列表项与命名块已由展平处理）。"""
    content = getattr(block, "content", None)
    if not isinstance(content, list) or not content:
        return []
    if isinstance(content[0], BlockNode_ALIAS):  # 块级内容交给 iter_blocks
        return []
    result: list[InlineNode] = []
    for node in content:
        result.append(node)
        nested = getattr(node, "content", None)
        if isinstance(nested, list) and nested and not isinstance(nested[0], BlockNode_ALIAS):
            result.extend(nested)
    return result


#: 用于区分「块级 content」与「行内 content」的标记类型
BlockNode_ALIAS = (NamedBlock, ListBlock, BlockQuote)


def caption_counters(blocks: list[BlockNode]) -> dict[str, int]:
    """按类型独立计数：``{label: 序号}``（图 1、图 2、表 1……）。"""
    counters: dict[str, int] = {}
    per_kind: dict[str, int] = {}
    for block in iter_blocks(blocks):
        if isinstance(block, NamedBlock) and block.label:
            kind = caption_kind(block)
            per_kind[kind] = per_kind.get(kind, 0) + 1
            counters[block.label] = per_kind[kind]
    return counters


def caption_number(blocks: list[BlockNode], label: str) -> int | None:
    """某个标签的题注序号（不存在返回 None）。"""
    return caption_counters(blocks).get(label)


def baked_fields(blocks: list[BlockNode]) -> dict[str, str]:
    """标签 -> **域缓存值**（写进 docx 里的字面结果）。

    为什么需要：Word 打开文档时会按 ``updateFields`` 重算域，所以缓存值写错也
    看不出来；但 WPS / Office 预览 / 网页版 / 任何按文本读的转换链路看到的
    就是缓存值。原先所有域都写死 ``"1"``，于是整篇图号都显示「图 1」（实测反馈）。

    - 题注（``captions``）：``SEQ 图`` 的结果 = 该类型内的序号；
    - 编号公式：书签包住的是 ``(N)``，所以引用它的缓存值也带括号；
    - 其它带 ``#id`` 的命名块：按题注序号。
    """
    counters = caption_counters(blocks)
    baked: dict[str, str] = {}
    for block in iter_blocks(blocks):
        if not isinstance(block, NamedBlock) or not block.label:
            continue
        number = block.attributes.get("number")
        if block.name == "equation":
            # 编号公式的书签包住 ``(N)``；无 number 的公式没有编号，也没有书签，
            # 不能凭空烘出一个数字来（引用它会由 REF 域自行重算/报错）
            if number:
                baked[block.label] = f"({number})"
        elif block.label in counters:
            baked[block.label] = str(counters[block.label])
    return baked


def validate_numbering(
    blocks: list[BlockNode], config: Config, source: str = ""
) -> list[ContentError]:
    """检查交叉引用目标与标签唯一性。"""
    errors: list[ContentError] = []
    labels: dict[str, int] = {}
    for block in iter_blocks(blocks):
        if isinstance(block, NamedBlock) and block.label:
            if block.label in labels:
                errors.append(
                    ContentError(
                        code=E_SYNTAX,
                        message=f"标签重复: {block.label}（首次出现在第 {labels[block.label]} 行）",
                        file=source,
                        line=block.source_line,
                    )
                )
            else:
                labels[block.label] = block.source_line

    for ref in collect_refs(blocks):
        if ref.target not in labels:
            errors.append(
                ContentError(
                    code=E_UNKNOWN_REF,
                    message=f"交叉引用不存在: {ref.target}",
                    file=source,
                    line=ref.source_line,
                )
            )
    return errors

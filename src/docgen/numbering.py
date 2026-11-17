"""编号 / 题注 / 交叉引用。

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
from .errors import E_CONFIG, E_SYNTAX, E_UNKNOWN_REF, DocGenError
from .ir import BlockNode, BlockQuote, Formula, Heading, InlineNode, ListBlock, NamedBlock, Ref
from .validate import ContentError

__all__ = [
    "CAPTION_KINDS",
    "CaptionRef",
    "RefUse",
    "baked_fields",
    "baked_heading_labels",
    "caption_counters",
    "caption_kind",
    "caption_numbering_mode",
    "caption_numbers",
    "collect_labels",
    "collect_refs",
    "equation_numbering_mode",
    "equation_numbers",
    "format_heading_label",
    "heading_numbering",
    "heading_numbering_mode",
    "toc_levels",
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


#: 标题编号预设：``decimal`` = Word 多级编号 1 / 1.1 / 1.1.1（默认，不烘焙）；
#: ``chapter`` = 第一章 / 1.1 / 1.1.1；``chinese`` = 一、 / （一） / 1. / （1）
HEADING_NUMBERING_MODES = ("decimal", "chapter", "chinese")

_CN_DIGITS = ("零", "一", "二", "三", "四", "五", "六", "七", "八", "九")


def _cn_number(value: int) -> str:
    """1–99 → 中文数字（一 / 十二 / 二十三）；超出范围退回阿拉伯数字。"""
    if value <= 0 or value >= 100:
        return str(value)
    if value < 10:
        return _CN_DIGITS[value]
    tens, ones = divmod(value, 10)
    prefix = "" if tens == 1 else _CN_DIGITS[tens]
    return prefix + "十" + (_CN_DIGITS[ones] if ones else "")


def heading_numbering_mode(config: Config) -> str:
    """``[document] heading_numbering`` → ``off`` / ``decimal`` / ``chapter`` / ``chinese``。

    兼容旧写法：``true``（= decimal）、``false``（= off）、
    ``heading_numbering.enabled = false`` 以及 ``heading_numbering.style = "chapter"``。
    """
    raw = config.setting("heading_numbering", True)
    if isinstance(raw, dict):
        if not raw.get("enabled", True):
            return "off"
        raw = raw.get("style", "decimal")
    if isinstance(raw, bool):
        return "decimal" if raw else "off"
    text = str(raw).strip().lower()
    aliases = {
        "true": "decimal",
        "1": "decimal",
        "yes": "decimal",
        "on": "decimal",
        "false": "off",
        "0": "off",
        "no": "off",
        "off": "off",
        "decimal": "decimal",
        "chapter": "chapter",
        "chinese": "chinese",
    }
    if text in aliases:
        return aliases[text]
    raise DocGenError(
        E_CONFIG,
        f"[document] heading_numbering 不支持: {raw!r}"
        "（可用 true/false 或 decimal / chapter / chinese）",
    )


def format_heading_label(mode: str, level: int, counters: list[int]) -> str:
    """按预设生成一级标题编号文本；``counters[1..9]`` 是各级当前计数。"""
    if mode == "chapter":
        if level == 1:
            return f"第{_cn_number(counters[1])}章"
        return ".".join(str(counters[index]) for index in range(1, level + 1))
    if mode == "chinese":
        if level == 1:
            return f"{_cn_number(counters[1])}、"
        if level == 2:
            return f"（{_cn_number(counters[2])}）"
        if level == 3:
            return f"{counters[3]}."
        if level == 4:
            return f"（{counters[4]}）"
        return f"{counters[level]})"
    return ".".join(str(counters[index]) for index in range(1, level + 1))


def toc_levels(config: Config) -> str:
    r"""``[toc] levels`` → TOC 域的 ``\o "A-B"`` 参数（默认 ``1-9``）。

    ``levels = 3`` 等价于 ``1-3``；也可写字符串 ``"2-4"``。范围 1–9，非法值报 E5001。
    """
    raw = config.namespace("toc").get("levels", "1-9")
    if isinstance(raw, bool):
        raise DocGenError(E_CONFIG, f"[toc] levels 不能是布尔值: {raw!r}")
    if isinstance(raw, int):
        start, end = 1, raw
    else:
        text = str(raw).strip()
        if "-" in text:
            left, _, right = text.partition("-")
            try:
                start, end = int(left), int(right)
            except ValueError:
                raise DocGenError(
                    E_CONFIG, f'[toc] levels 无法识别: {raw!r}（可用 3 或 "1-3"）'
                ) from None
        else:
            try:
                start, end = 1, int(text)
            except ValueError:
                raise DocGenError(
                    E_CONFIG, f'[toc] levels 无法识别: {raw!r}（可用 3 或 "1-3"）'
                ) from None
    if not (1 <= start <= end <= 9):
        raise DocGenError(E_CONFIG, f"[toc] levels 需要在 1–9 且 start<=end: {raw!r}")
    return f"{start}-{end}"


def equation_numbering_mode(config: Config) -> str:
    """``[math] numbering``：``none``（默认，仅手动 number）/ ``auto`` / ``chapter``。"""
    raw = config.namespace("math").get("numbering", "none")
    if isinstance(raw, bool):
        return "auto" if raw else "none"
    text = str(raw).strip().lower()
    aliases = {
        "none": "none",
        "false": "none",
        "off": "none",
        "0": "none",
        "auto": "auto",
        "true": "auto",
        "1": "auto",
        "chapter": "chapter",
        "by-chapter": "chapter",
    }
    if text in aliases:
        return aliases[text]
    raise DocGenError(
        E_CONFIG,
        f"[math] numbering 不支持: {raw!r}（可用 none / auto / chapter）",
    )


def equation_numbers(blocks: list[BlockNode], config: Config) -> dict[int, str]:
    """公式块 -> 编号文本（``id(NamedBlock)`` 关联）。

    - 手动 ``number=...`` 优先（也支持非数字，如 ``2-1``）；
    - ``numbering = "auto"``：按出现顺序 1、2、3…；
    - ``numbering = "chapter"``：按一级标题分章，编号「章-序」（2-1）。
    只处理含 ``Formula`` 子节点的 ``\begin{equation}``；普通 ``$$…$$`` 不参与。
    """
    mode = equation_numbering_mode(config)
    numbers: dict[int, str] = {}
    chapter = 0
    counter = 0
    for block in iter_blocks(blocks):
        if isinstance(block, Heading):
            if max(1, min(9, block.level)) == 1:
                chapter += 1
                counter = 0
            continue
        if not isinstance(block, NamedBlock) or block.name != "equation":
            continue
        if not any(isinstance(child, Formula) for child in block.content):
            continue
        manual = str(block.attributes.get("number", "") or "")
        if manual:
            numbers[id(block)] = manual
            if manual.isdigit():
                counter = max(counter, int(manual))
            continue
        if mode == "none":
            continue
        counter += 1
        numbers[id(block)] = (
            f"{chapter}-{counter}" if mode == "chapter" and chapter > 0 else str(counter)
        )
    return numbers


def baked_heading_labels(blocks: list[BlockNode], config: Config) -> dict[int, str]:
    """自定义标题编号（chapter/chinese）在构建期算成文本；decimal/off 返回空表。

    返回 ``{id(Heading 节点): 编号文本}``——节点是 frozen dataclass，用 ``id`` 关联；
    渲染时同一次构建内对象不会回收，安全。
    """
    mode = heading_numbering_mode(config)
    if mode in ("off", "decimal"):
        return {}
    counters = [0] * 10
    labels: dict[int, str] = {}
    for block in iter_blocks(blocks):
        if not isinstance(block, Heading):
            continue
        level = max(1, min(9, block.level))
        counters[level] += 1
        for deeper in range(level + 1, 10):
            counters[deeper] = 0
        labels[id(block)] = format_heading_label(mode, level, counters)
    return labels


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


def caption_numbering_mode(config: Config) -> str:
    """``[document] caption_numbering``：``continuous``（默认）或 ``chapter``。"""
    raw = config.setting("caption_numbering", "continuous")
    if isinstance(raw, bool):
        return "chapter" if raw else "continuous"
    text = str(raw).strip().lower()
    aliases = {
        "continuous": "continuous",
        "false": "continuous",
        "off": "continuous",
        "0": "continuous",
        "chapter": "chapter",
        "by-chapter": "chapter",
        "true": "chapter",
        "1": "chapter",
    }
    if text in aliases:
        return aliases[text]
    raise DocGenError(
        E_CONFIG,
        f"[document] caption_numbering 不支持: {raw!r}（可用 continuous / chapter）",
    )


def caption_numbers(blocks: list[BlockNode], config: Config) -> dict[str, str]:
    """题注标签 → 显示编号：连续模式 ``"3"``，按章模式 ``"2-1"``。

    ``chapter`` 模式以一级标题（Heading 1）分章；第一个一级标题之前的内容算
    「第 0 章」，题注不加章号前缀（保持连续编号），避免出现「0-1」。
    公式（``equation``）不参与：它的编号由 ``number`` 属性手写。
    """
    mode = caption_numbering_mode(config)
    if mode != "chapter":
        return {label: str(number) for label, number in caption_counters(blocks).items()}

    chapter = 0
    local: dict[str, int] = {}
    numbers: dict[str, str] = {}
    for block in iter_blocks(blocks):
        if isinstance(block, Heading):
            if max(1, min(9, block.level)) == 1:
                chapter += 1
                local = {}
            continue
        if not isinstance(block, NamedBlock) or not block.label:
            continue
        kind = caption_kind(block)
        if kind == "equation":
            continue
        local[kind] = local.get(kind, 0) + 1
        numbers[block.label] = f"{chapter}-{local[kind]}" if chapter > 0 else str(local[kind])
    return numbers


def caption_number(blocks: list[BlockNode], label: str) -> int | None:
    """某个标签的题注序号（不存在返回 None）。"""
    return caption_counters(blocks).get(label)


def baked_fields(blocks: list[BlockNode], config: Config | None = None) -> dict[str, str]:
    """标签 -> **域缓存值**（写进 docx 里的字面结果）。

    为什么需要：Word 打开文档时会按 ``updateFields`` 重算域，所以缓存值写错也
    看不出来；但 WPS / Office 预览 / 网页版 / 任何按文本读的转换链路看到的
    就是缓存值。原先所有域都写死 ``"1"``，于是整篇图号都显示「图 1」（实测反馈）。

    - 题注（``captions``）：``SEQ 图`` 的结果 = 该类型内的序号；
    - 编号公式：书签包住的是 ``(N)``，所以引用它的缓存值也带括号；
    - 其它带 ``#id`` 的命名块：按题注序号。
    """
    if config is None:
        counters: dict[str, str] = {
            label: str(number) for label, number in caption_counters(blocks).items()
        }
        equations: dict[int, str] = {}
    else:
        counters = caption_numbers(blocks, config)
        equations = equation_numbers(blocks, config)
    baked: dict[str, str] = {}
    for block in iter_blocks(blocks):
        if not isinstance(block, NamedBlock) or not block.label:
            continue
        number = block.attributes.get("number")
        if block.name == "equation":
            # 编号公式的书签包住 ``(N)``；手动 number 优先，其次自动/按章编号
            value = equations.get(id(block)) or (str(number) if number else "")
            if value:
                baked[block.label] = f"({value})"
        elif block.label in counters:
            baked[block.label] = counters[block.label]
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

"""``\\begin{...} ... \\end{...}`` 预扫描（完整版手册 §6.2.5）。

CommonMark 的 fence 长度规则对 LLM 不友好：内部含 ``` 或需要嵌套同类结构时，
fence 会提前终止。所以 DFM 提供第二套语法，**在交给 markdown-it 之前**处理：

- ``\\begin{code:lang} ... \\end{code:lang}`` → 与 fence 等价的代码块（内容原样保留）
- ``\\begin{名字 属性} ... \\end{名字}`` → 命名块容器，内容按 DFM 继续解析（可嵌套）

实现要点：

1. ``\\begin{...}`` 必须**独占一行**（可含前后空白）；行内出现就是普通文本。
2. 边界行被替换成同形的**占位行**，保证 markdown-it 看到的行号与源文件一致
   （IR 的 ``source_line`` 契约依赖这一点）。
3. 首尾名字必须一致 → ``E3002``；缺 ``\\end`` → ``E3001``；属性语法非法 → ``E4001``。
4. 命名块内部递归预扫描，所以嵌套命名块可用；``code:`` 块内部不递归（原样保留）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..errors import E_BEGIN_MISMATCH, E_SYNTAX, E_UNCLOSED_MARKER, DocGenError
from ..ir import BlockNode, CodeBlock, NamedBlock

__all__ = [
    "BEGIN_PLACEHOLDER",
    "BeginBlock",
    "Placeholder",
    "extract_begin_blocks",
    "parse_begin_block",
]

#: 占位行携带的标记。用文本哨兵而不是 HTML 注释：注释会被 markdown-it 当成
#: ``html_block`` 丢掉，而这段「普通文字」会稳定地变成一个段落（单 text 子节点）。
BEGIN_PLACEHOLDER = "docgen-begin-block-"

_BEGIN_RE = re.compile(r"^\s*\\begin\{([^{}]*)\}\s*$")
_END_RE = re.compile(r"^\s*\\end\{([^{}]*)\}\s*$")


@dataclass(frozen=True)
class BeginBlock:
    """预扫描得到的一个 ``\\begin`` 块。"""

    name: str
    attributes: dict[str, str]
    body: str
    source_line: int
    is_code: bool
    language: str = ""


@dataclass(frozen=True)
class Placeholder:
    """占位行：指向预扫描得到的块。"""

    index: int


def extract_begin_blocks(text: str) -> tuple[str, list[BeginBlock]]:
    """把 ``\\begin`` 块抽出来，返回 ``(替换占位后的文本, 块列表)``。

    文本行数与源文件一致（占位行一对一替换多行区域）。
    """
    lines = text.split("\n")
    output: list[str] = []
    blocks: list[BeginBlock] = []
    index = 0

    while index < len(lines):
        match = _BEGIN_RE.match(lines[index])
        if match is None:
            output.append(lines[index])
            index += 1
            continue

        raw_name = match.group(1).strip()
        if output and output[-1].strip():
            # 手册 §6.2.5：\begin 必须独占一行；与上一行之间没有空行说明它夹在段落里
            raise DocGenError(
                E_SYNTAX,
                f"\\begin{{{raw_name}}} 必须独占一行（前面需要一个空行）",
                line=index + 1,
            )
        name, attributes = _split_name(raw_name, index + 1)
        body_lines: list[str] = []
        depth = 1
        cursor = index + 1
        while cursor < len(lines):
            begin_here = _BEGIN_RE.match(lines[cursor])
            end_here = _END_RE.match(lines[cursor])
            if begin_here is not None:
                depth += 1
            elif end_here is not None:
                depth -= 1
                if depth == 0:
                    break
            body_lines.append(lines[cursor])
            cursor += 1

        if cursor >= len(lines):
            raise DocGenError(
                E_UNCLOSED_MARKER,
                f"未闭合的 \\begin{{{raw_name}}}",
                line=index + 1,
            )

        closing = _END_RE.match(lines[cursor])
        assert closing is not None
        if closing.group(1).strip() != raw_name.split(None, 1)[0]:
            raise DocGenError(
                E_BEGIN_MISMATCH,
                f"\\begin 与 \\end 名字不一致: {raw_name!r} vs {closing.group(1).strip()!r}",
                line=cursor + 1,
            )

        is_code = name.startswith("code")
        language = _code_language(name)
        block_index = len(blocks)
        blocks.append(
            BeginBlock(
                name=name,
                attributes=attributes,
                body="\n".join(body_lines) + "\n" if body_lines else "",
                source_line=index + 1,
                is_code=is_code,
                language=language,
            )
        )
        output.append(f"{BEGIN_PLACEHOLDER}{block_index}")
        # 边界行之外的行清空（保留行数，让占位行与后继内容的行号都不变）
        output.extend("" for _ in range(cursor - index))
        index = cursor + 1

    return "\n".join(output), blocks


def _split_name(raw: str, line: int) -> tuple[str, dict[str, str]]:
    """``code:python`` / ``caption`` / ``equation #eq:main .numbered`` → 名字 + 属性。"""
    raw = raw.strip()
    if not raw:
        raise DocGenError(E_SYNTAX, "\\begin{} 缺少名字", line=line)

    parts = raw.split(None, 1)
    name = parts[0]
    attributes = parse_attributes(parts[1]) if len(parts) > 1 else {}
    return name, attributes


def parse_attributes(raw: str) -> dict[str, str]:
    """解析 Pandoc 属性语法：``{.class #id key=value}`` / ``.class #id``。"""
    text = raw.strip()
    if text.startswith("{") and text.endswith("}"):
        text = text[1:-1]
    attributes: dict[str, str] = {}
    classes: list[str] = []

    for token in text.split():
        if token.startswith("."):
            classes.append(token[1:])
        elif token.startswith("#"):
            attributes["id"] = token[1:]
        elif "=" in token:
            key, _, value = token.partition("=")
            attributes[key.strip()] = value.strip().strip('"')
        elif token:
            classes.append(token)

    if classes:
        attributes["classes"] = " ".join(classes)
    return attributes


def _code_language(name: str) -> str:
    _, _, language = name.partition(":")
    return language.strip()


def parse_begin_block(block: BeginBlock) -> BlockNode:
    """把一个预扫描块变成 IR 节点（命名块内容递归解析）。

    命名块内部的行号是**相对块首**的（内容被单独解析）；需要绝对行号时
    用块的 ``source_line`` 作偏移。
    """
    if block.is_code:
        return CodeBlock(
            language=block.language,
            content=block.body,
            source_line=block.source_line,
        )

    from .dfm import parse_dfm  # 延迟导入避免循环

    return NamedBlock(
        name=block.name,
        content=parse_dfm(block.body),
        attributes=block.attributes,
        label=block.attributes.get("id", ""),
        source_line=block.source_line,
    )

"""诊断（第 3 周）：把「宽容解析」留下的问题变成结构化错误码。

解析器不会因为未闭合标记失败（内容退化为字面文本，不丢东西），但**用户需要知道**。
所以诊断单独成层，只依赖源文本 + IR，供 ``check`` 使用：

- ``E3001`` 标记未闭合（``[[`` / ``[...]{...}`` / ``$...$`` / ``$$...$$`` / 围栏）
- ``E2001`` 未知语言（代码围栏的 info 不在语言白名单里）
- ``E4001`` 语法错误（围栏未配对等）

扫描规则与解析器保持一致：忽略围栏与行内代码里的标记、支持 ``\\`` 转义、
``$$`` 优先于 ``$``、``$`` 后接数字不当作数学（``$5 元`` 是文本）。
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from .config import Config
from .errors import (
    E_SYNTAX,
    E_UNCLOSED_MARKER,
    E_UNKNOWN_LANGUAGE,
)
from .ir import BlockNode, CodeBlock
from .validate import ContentError, validate_content

__all__ = [
    "DEFAULT_LANGUAGES",
    "DIAGNOSTIC_KINDS",
    "SOURCE_ERROR_KINDS",
    "format_content_error",
    "scan_diagnostics",
    "scan_source",
    "with_diagnostics",
]

SOURCE_ERROR_KINDS = ("unclosed", "fence")
DIAGNOSTIC_KINDS = ("unclosed", "fence", "language")

#: 代码块允许的语言（小写）；不在表里报 ``E2001``。空 info 表示纯文本，始终允许。
DEFAULT_LANGUAGES: frozenset[str] = frozenset(
    {
        "bash",
        "c",
        "cpp",
        "csharp",
        "css",
        "diff",
        "dockerfile",
        "go",
        "html",
        "ini",
        "java",
        "javascript",
        "json",
        "js",
        "jsx",
        "kotlin",
        "latex",
        "lua",
        "makefile",
        "markdown",
        "md",
        "php",
        "plaintext",
        "powershell",
        "ps1",
        "py",
        "python",
        "ruby",
        "rust",
        "sh",
        "shell",
        "sql",
        "swift",
        "text",
        "toml",
        "ts",
        "tsx",
        "typescript",
        "xml",
        "yaml",
        "yml",
        "zsh",
    }
)

_FENCE_CHARS = ("`", "~")


def format_content_error(error: ContentError, source: str | None = None) -> str:
    """补上文件名后的 ``file:line:col:code:message`` 文本。"""
    if source is None:
        return str(error)
    return (
        f"{source}:{error.line}:{error.col}:{error.code}:{error.message}"
        if error.line
        else f"{source}:{error.code}:{error.message}"
    )


def with_diagnostics(
    text: str,
    blocks: list[BlockNode],
    config: Config,
    source: str | None = None,
    base_dir: Path | None = None,
) -> list[ContentError]:
    """校验（样式/图片）+ 诊断（未闭合/未知语言/语法），按行号排序。"""
    merged = [
        *validate_content(blocks, config, base_dir=base_dir),
        *scan_diagnostics(text, blocks),
    ]
    if source is not None:
        merged = [
            ContentError(
                code=err.code,
                message=err.message,
                file=source,
                line=err.line,
                col=err.col,
            )
            for err in merged
        ]
    return sorted(merged, key=lambda err: (err.line, err.col, err.code))


def scan_diagnostics(
    text: str,
    blocks: list[BlockNode],
    languages: frozenset[str] = DEFAULT_LANGUAGES,
) -> list[ContentError]:
    """源文本诊断 + 依赖 IR 的语言诊断。"""
    return sorted(
        [*scan_source(text, DIAGNOSTIC_KINDS), *_scan_languages(blocks, languages)],
        key=lambda err: (err.line, err.col, err.code),
    )


def _scan_languages(blocks: list[BlockNode], languages: frozenset[str]) -> list[ContentError]:
    found: list[ContentError] = []
    for block in _walk_blocks(blocks):
        if not isinstance(block, CodeBlock):
            continue
        language = block.language.strip().lower()
        if not language or language in languages:
            continue
        found.append(
            ContentError(
                code=E_UNKNOWN_LANGUAGE,
                message=f"未知语言: {block.language}",
                line=block.source_line,
                col=1,
            )
        )
    return found


def _walk_blocks(blocks: list[BlockNode]) -> list[BlockNode]:
    """展平嵌套块（引用、列表项）以便检查其中的代码块。"""
    from .ir import BlockQuote, ListBlock

    flat: list[BlockNode] = []
    for block in blocks:
        flat.append(block)
        if isinstance(block, BlockQuote):
            flat.extend(_walk_blocks(block.content))
        elif isinstance(block, ListBlock):
            for item in block.items:
                flat.extend(_walk_blocks(item.content))
    return flat


# --------------------------------------------------------------------------
# 源文本扫描
# --------------------------------------------------------------------------
def scan_source(text: str, kinds: Sequence[str] = SOURCE_ERROR_KINDS) -> list[ContentError]:
    """整篇扫描（跳过围栏、行内代码与块级公式），报告未闭合标记与围栏语法错误。

    状态机维护两种跨行上下文：``\\`\\`\\` `` 围栏与 ``$$`` 块级公式；
    只有上下文之外的文本才逐行做标记配对检查。
    """
    found: list[ContentError] = []
    fence: str | None = None
    fence_line = 0
    block_math = False
    block_math_line = 0

    for number, line in enumerate(text.split("\n"), start=1):
        if fence is not None:
            marker = _fence_marker(line)
            if marker == fence:
                fence = None
            continue

        marker = _fence_marker(line)
        if marker is not None:
            fence, fence_line = marker, number
            continue

        if block_math:
            if line.strip().endswith("$$"):
                block_math = False
            continue

        if _opens_block_math(line):
            block_math, block_math_line = True, number
            continue

        if "unclosed" in kinds:
            found.extend(_scan_line(_mask_code_spans(line), number, marker_col_offset=1))

    if fence is not None and "fence" in kinds:
        found.append(
            ContentError(
                code=E_SYNTAX,
                message=f"代码围栏未闭合: {fence * 3}",
                line=fence_line,
                col=1,
            )
        )
    if block_math and "unclosed" in kinds:
        found.append(
            ContentError(
                code=E_UNCLOSED_MARKER,
                message="未闭合的标记: $$",
                line=block_math_line,
                col=1,
            )
        )
    return sorted(found, key=lambda err: (err.line, err.col, err.code))


def _opens_block_math(line: str) -> bool:
    """独立一行的 ``$$`` 打开块级公式（闭合由后续行负责）。"""
    stripped = line.strip()
    return stripped == "$$" or (stripped.startswith("$$") and not stripped.endswith("$$"))


def _fence_marker(line: str) -> str | None:
    stripped = line.lstrip()
    if len(stripped) < 3:
        return None
    for char in _FENCE_CHARS:
        if stripped.startswith(char * 3):
            return char
    return None


def _mask_code_spans(line: str) -> str:
    """把行内代码 `` `...` `` 替换成同长度的占位，避免在代码里误报。"""
    chars = list(line)
    index = 0
    while index < len(chars):
        if chars[index] == "\\":
            index += 2
            continue
        if chars[index] == "`":
            close = line.find("`", index + 1)
            if close == -1:
                break
            for position in range(index, close + 1):
                chars[position] = "\x00"
            index = close + 1
            continue
        index += 1
    return "".join(chars)


def _scan_line(line: str, number: int, marker_col_offset: int) -> list[ContentError]:
    found: list[ContentError] = []
    index = 0
    length = len(line)

    while index < length:
        char = line[index]
        if char == "\\":
            index += 2
            continue
        if char == "[" and line.startswith("[[", index):
            close = _find_unescaped(line, "]]", index + 2)
            if close == -1:
                found.append(_unclosed(number, index + marker_col_offset, "[["))
                break
            index = close + 2
            continue
        if char == "[":
            close = _find_unescaped(line, "]", index + 1)
            if close != -1 and line[close + 1 : close + 2] == "{":
                brace = _find_unescaped(line, "}", close + 2)
                if brace == -1:
                    found.append(_unclosed(number, index + marker_col_offset, "[...]{"))
                    break
                if not _style_name_of(line[close + 2 : brace]):
                    found.append(_unclosed(number, index + marker_col_offset, "[...]{}"))
                    break
                index = brace + 1
                continue
        if char == "$":
            if line.startswith("$$", index):
                close = _find_unescaped(line, "$$", index + 2)
                if close == -1:
                    found.append(_unclosed(number, index + marker_col_offset, "$$"))
                    break
                index = close + 2
                continue
            if _looks_like_inline_math(line, index):
                close = _find_unescaped(line, "$", index + 1)
                if close == -1:
                    found.append(_unclosed(number, index + marker_col_offset, "$"))
                    break
                index = close + 1
                continue
        index += 1

    return found


def _find_unescaped(line: str, needle: str, start: int) -> int:
    index = start
    while True:
        found = line.find(needle, index)
        if found == -1:
            return -1
        backslashes = 0
        position = found - 1
        while position >= 0 and line[position] == "\\":
            backslashes += 1
            position -= 1
        if backslashes % 2 == 0:
            return found
        index = found + len(needle)


def _style_name_of(raw: str) -> bool:
    name = raw.strip().lstrip(".#")
    return bool(name) and all(ch.isalnum() or ch in "_-." for ch in name)


def _looks_like_inline_math(line: str, index: int) -> bool:
    """``$`` 后必须是可作数学起始的字符：空白或数字不算（``$5 元`` 是文本）。"""
    after = line[index + 1 : index + 2]
    return bool(after) and not after.isspace() and not after.isdigit()


def _unclosed(line_number: int, column: int, marker: str) -> ContentError:
    return ContentError(
        code=E_UNCLOSED_MARKER,
        message=f"未闭合的标记: {marker}",
        line=line_number,
        col=column,
    )

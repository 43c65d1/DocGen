"""语义校验（手册 §6 / 第 2 周）。

校验发生在「解析出 IR 之后、渲染之前」。当前检查两类内容错误：

- ``E1003`` 引用了 config 里不存在的样式（``[文字]{.样式名}``）
- ``E5001`` 图片路径不存在（``[[img:path]]``，含行内图片与独立图片块）

返回错误列表而不是抛异常：``check --json`` 需要一次性报告全部问题。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import BUILTIN_STYLES, Config
from .errors import E_CONFIG, E_UNKNOWN_STYLE
from .ir import (
    BlockNode,
    BlockQuote,
    Heading,
    Image,
    ImageBlock,
    InlineNode,
    ListBlock,
    ListItem,
    Paragraph,
    Styled,
)

__all__ = ["ContentError", "validate_content"]

IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".bmp")

_INLINE_BLOCK_TYPES = (Heading, Paragraph)


@dataclass(frozen=True)
class ContentError:
    code: str
    message: str
    file: str = ""
    line: int = 0
    col: int = 0

    def __str__(self) -> str:
        if self.file:
            return f"{self.file}:{self.line}:{self.col}:{self.code}:{self.message}"
        return f"{self.code}:{self.message}"

    def as_dict(self) -> dict[str, object]:
        return {
            "file": self.file,
            "line": self.line,
            "col": self.col,
            "code": self.code,
            "message": self.message,
        }


def validate_content(
    blocks: list[BlockNode],
    config: Config,
    source: Path | None = None,
    base_dir: Path | None = None,
) -> list[ContentError]:
    """检查样式引用与图片路径，返回全部错误（可能为空）。"""
    file_name = str(source) if source is not None else ""
    root = base_dir if base_dir is not None else (source.parent if source else Path())
    known_styles = (
        set(config.styles) | set(BUILTIN_STYLES) | {"code_block"} | set(config.code_blocks)
    )

    errors: list[ContentError] = []

    def check_image(src: str, line: int) -> None:
        if not src or "://" in src or src.startswith("data:"):
            return  # 远程地址与内联数据不检查本地文件
        if not src.lower().endswith(IMAGE_SUFFIXES):
            return
        if not (root / src).is_file():
            errors.append(
                ContentError(
                    code=E_CONFIG,
                    message=f"图片不存在: {src}",
                    file=file_name,
                    line=line,
                )
            )

    def check_inline(nodes: list[InlineNode], line: int) -> None:
        for node in nodes:
            if isinstance(node, Styled):
                if node.style_name not in known_styles:
                    errors.append(
                        ContentError(
                            code=E_UNKNOWN_STYLE,
                            message=f"引用了不存在的样式: {node.style_name}",
                            file=file_name,
                            line=line,
                        )
                    )
                check_inline(node.content, line)
            elif isinstance(node, Image):
                check_image(node.src, line)

    def check_blocks(nodes: list[BlockNode], fallback_line: int) -> None:
        for node in nodes:
            line = node.source_line or fallback_line
            if isinstance(node, BlockQuote):
                check_blocks(node.content, line)
            elif isinstance(node, ListBlock):
                for item in node.items:
                    check_items(item, line)
            elif isinstance(node, ImageBlock):
                check_image(node.src, line)
            elif isinstance(node, _INLINE_BLOCK_TYPES):
                check_inline(node.content, line)

    def check_items(item: ListItem, fallback_line: int) -> None:
        for child in item.content:
            line = child.source_line or fallback_line
            if isinstance(child, _INLINE_BLOCK_TYPES):
                check_inline(child.content, line)
            elif isinstance(child, BlockQuote):
                check_blocks(child.content, line)
            elif isinstance(child, ListBlock):
                for nested in child.items:
                    check_items(nested, line)
            elif isinstance(child, ImageBlock):
                check_image(child.src, line)

    check_blocks(blocks, 0)
    return errors

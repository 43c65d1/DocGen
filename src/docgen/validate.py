"""语义校验（手册 §6 / 第 2 周）。

校验发生在「解析出 IR 之后、渲染之前」。当前检查两类内容错误：

- ``E1003`` 引用了 config 里不存在的样式（``[文字]{.样式名}``）
- ``E5001`` 图片路径不存在（``[[img:path]]``，含行内图片与独立图片块）

返回错误列表而不是抛异常：``check --json`` 需要一次性报告全部问题。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import BUILTIN_STYLES, INLINE_STYLE_NAMES, Config
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

#: 语义名 -> 触发它的 Markdown/DFM 写法，用于把映射链讲清楚
#: （需求：「报错暴露映射链」——既要说明是哪个语法，也要说明它现在指向谁）
INLINE_SYNTAX_HINTS: dict[str, str] = {
    "strong": "**粗体**",
    "em": "*斜体*",
    "strike": "~~删除~~",
    "sup": "^上标^ 或 [文字]{.sup}",
    "sub": "~下标~ 或 [文字]{.sub}",
}


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
    """检查样式引用与图片路径，返回全部错误（可能为空）。

    ``[inline]`` 映射会一并展开：``sup = "sup_caret"`` 时，
    检查的是**映射后的实际样式名** ``sup_caret``，报错信息里带上映射链。
    """
    file_name = str(source) if source is not None else ""
    root = base_dir if base_dir is not None else (source.parent if source else Path())
    mapping = config.inline_mapping()
    # 已知样式 = 显式声明的 + 内置语义名。
    # **不能**把 mapping.values() 也算进来：``sup = "sup_caret"`` 而没声明
    # ``[styles.sup_caret]`` 时必须报错（需求要求暴露映射链），
    # 否则重定向会把「样式缺失」静默吞掉。
    known_styles = (
        set(config.styles) | set(BUILTIN_STYLES) | {"code_block"} | set(config.code_blocks)
    )
    errors: list[ContentError] = []

    def style_error(semantic: str, line: int) -> ContentError:
        """构造「样式不存在」的错误；语义名带映射时把映射链写给用户。"""
        target = mapping.get(semantic, semantic)
        if target != semantic:
            syntax = INLINE_SYNTAX_HINTS.get(semantic, semantic)
            message = (
                f"{syntax} 映射到 {target}"
                f"（来自 [inline].{semantic}），但 config 缺少 [styles.{target}]"
            )
        elif semantic in INLINE_STYLE_NAMES:
            syntax = INLINE_SYNTAX_HINTS.get(semantic, semantic)
            message = f"{syntax} 使用的样式 {semantic} 未在 config 中声明 [styles.{semantic}]"
        else:
            message = f"引用了不存在的样式: {semantic}"
        return ContentError(code=E_UNKNOWN_STYLE, message=message, file=file_name, line=line)

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
                # 语义名先按 [inline] 映射成实际样式名，再查样式表
                target = mapping.get(node.style_name, node.style_name)
                if target not in known_styles:
                    errors.append(style_error(node.style_name, line))
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

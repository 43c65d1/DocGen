"""DocGen 中间表示（IR）。

契约（手册 5.2）：

- 所有节点是 ``frozen`` dataclass：按值相等、不可变、字段全类型标注。
- 行内节点继承 :class:`Inline`，块级节点继承 :class:`Block`。
- 每个块级节点都带 ``source_line``（1 起，指向 DFM 源文件行号）。
- 字段名与 Markdown 语法无关，渲染层只认 IR。
"""

from dataclasses import dataclass, field

__all__ = [
    "Block",
    "BlockQuote",
    "Break",
    "Code",
    "CodeBlock",
    "Formula",
    "Heading",
    "Image",
    "ImageBlock",
    "Inline",
    "Link",
    "ListBlock",
    "ListItem",
    "Math",
    "PageBreak",
    "Paragraph",
    "Styled",
    "Table",
    "Text",
    "ThematicBreak",
]


# --------------------------------------------------------------------------
# 行内节点
# --------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class Inline:
    """行内节点基类：只作为类型标记，不携带字段。"""


@dataclass(frozen=True, slots=True)
class Text(Inline):
    content: str


@dataclass(frozen=True, slots=True)
class Styled(Inline):
    """``[文字]{.样式名}``：content 为样式作用域内的行内节点。"""

    content: list["InlineNode"]
    style_name: str


@dataclass(frozen=True, slots=True)
class Code(Inline):
    content: str


@dataclass(frozen=True, slots=True)
class Math(Inline):
    latex: str
    display: bool = False


@dataclass(frozen=True, slots=True)
class Link(Inline):
    url: str
    content: list["InlineNode"]


@dataclass(frozen=True, slots=True)
class Image(Inline):
    """``[[img:path]]``：src 为原始路径，alt 为可选替代文本。"""

    src: str
    alt: str = ""


@dataclass(frozen=True, slots=True)
class Break(Inline):
    """硬换行。"""


InlineNode = Text | Styled | Code | Math | Link | Image | Break


# --------------------------------------------------------------------------
# 块级节点
# --------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class Block:
    """块级节点基类：每个块级节点都必须能指回源行号。"""

    source_line: int


@dataclass(frozen=True, slots=True)
class Heading(Block):
    level: int
    content: list[InlineNode]


@dataclass(frozen=True, slots=True)
class Paragraph(Block):
    content: list[InlineNode]


@dataclass(frozen=True, slots=True)
class ListItem(Block):
    """列表项：内容本身是块级节点序列（支持嵌套列表）。"""

    content: list["BlockNode"] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ListBlock(Block):
    ordered: bool
    items: list[ListItem]


@dataclass(frozen=True, slots=True)
class CodeBlock(Block):
    language: str
    content: str


@dataclass(frozen=True, slots=True)
class Formula(Block):
    latex: str
    display: bool = True


@dataclass(frozen=True, slots=True)
class ImageBlock(Block):
    src: str
    alt: str = ""


@dataclass(frozen=True, slots=True)
class ThematicBreak(Block):
    """``---`` 分隔线。"""


@dataclass(frozen=True, slots=True)
class PageBreak(Block):
    """独立的 ``[[pagebreak]]``：与 ``---`` 不同，它是 DFM 自研的分页标记。"""


@dataclass(frozen=True, slots=True)
class BlockQuote(Block):
    content: list["BlockNode"]


@dataclass(frozen=True, slots=True)
class Table(Block):
    """简单表格：``rows`` 为单元格文本的行列表，第一行是表头。"""

    rows: list[list[str]]


BlockNode = (
    Heading
    | Paragraph
    | ListBlock
    | CodeBlock
    | Formula
    | ImageBlock
    | ThematicBreak
    | PageBreak
    | BlockQuote
    | Table
)

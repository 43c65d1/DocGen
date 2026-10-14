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
    "Footnote",
    "Formula",
    "Heading",
    "Image",
    "ImageBlock",
    "Inline",
    "Link",
    "ListBlock",
    "ListItem",
    "Math",
    "NamedBlock",
    "PageBreak",
    "Paragraph",
    "Ref",
    "Styled",
    "Table",
    "TableCell",
    "Text",
    "ThematicBreak",
    "Toc",
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


@dataclass(frozen=True, slots=True)
class Ref(Inline):
    """``[[ref:目标]]``：交叉引用（渲染成 Word 的 REF 域）。"""

    target: str


@dataclass(frozen=True, slots=True)
class Footnote(Inline):
    """``[[fn:文字]]``：行内脚注（渲染成引用 run + ``word/footnotes.xml`` 条目）。"""

    text: str


InlineNode = Text | Styled | Code | Math | Link | Image | Break | Ref | Footnote


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
    """独立一行的 ``[[img:path]]``；``width`` / ``align`` 来自属性或 config。"""

    src: str
    alt: str = ""
    width: str = ""
    align: str = ""


@dataclass(frozen=True, slots=True)
class ThematicBreak(Block):
    """``---`` 分隔线。"""


@dataclass(frozen=True, slots=True)
class PageBreak(Block):
    """独立的 ``[[pagebreak]]``：与 ``---`` 不同，它是 DFM 自研的分页标记。"""


@dataclass(frozen=True, slots=True)
class Toc(Block):
    """``[[toc]]``：目录占位（渲染成 Word 的 TOC 域）。"""


@dataclass(frozen=True, slots=True)
class NamedBlock(Block):
    """``\\begin{名字 属性} ... \\end{名字}``：命名块容器（题注、公式、摘要……）。

    ``attributes`` 来自 Pandoc 属性语法（``{.class #id key=value}``），
    解析成 ``{"classes": ..., "id": ..., 其它键: ...}``。``label`` 是 ``#id`` 的快捷取用，
    供 ``[[ref:...]]`` 交叉引用；``name`` 不含 ``code:`` 前缀——``\\begin{code:lang}``
    直接变成 :class:`CodeBlock`。
    """

    name: str
    content: list["BlockNode"] = field(default_factory=list)
    attributes: dict[str, str] = field(default_factory=dict)
    label: str = ""


@dataclass(frozen=True, slots=True)
class BlockQuote(Block):
    content: list["BlockNode"]


@dataclass(frozen=True, slots=True)
class TableCell:
    """表格单元格（支持合并）。

    ``blocks`` 是单元格内容（段落/列表/公式/图片），**禁止嵌套表格**，
    且块序列最多 2 层（手册 §6.3.2 的硬约束）。
    """

    blocks: list["BlockNode"] = field(default_factory=list)
    colspan: int = 1
    rowspan: int = 1
    is_merge_continuation: bool = False
    diag: int = 0
    diag_parts: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class Table(Block):
    """表格：``rows`` 是单元格文本行（GFM 简单表格），第一行是表头。

    ``cells`` 是结构化单元格（支持合并），给了它就优先于 ``rows``；
    ``alignments`` 来自 GFM 分隔行（``:---`` / ``:---:`` / ``---:``），
    每列取值 ``left`` / ``center`` / ``right``，空列表表示未声明。

    ``cell_nodes`` 是每个单元格的**行内 IR**（与 ``rows`` 同形状）：
    有了它，单元格里的加粗、行内代码、公式、链接才不会被拍平成纯文本。
    ``rows`` 保留原样文本，供不支持富文本的路径（如规范结构对比）使用。
    """

    rows: list[list[str]]
    cells: list[list[TableCell]] = field(default_factory=list)
    alignments: list[str] = field(default_factory=list)
    cell_nodes: list[list[list["InlineNode"]]] = field(default_factory=list)


BlockNode = (
    Heading
    | Paragraph
    | ListBlock
    | CodeBlock
    | Formula
    | ImageBlock
    | ThematicBreak
    | PageBreak
    | NamedBlock
    | Toc
    | BlockQuote
    | Table
)

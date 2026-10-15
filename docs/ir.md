# IR 参考

IR（中间表示）是 DocGen 的**稳定接口**：解析器只产出 IR，渲染器只消费 IR，
两侧都不认识对方的细节。定义在 [`src/docgen/ir.py`](../src/docgen/ir.py)。

## 不变量

1. **全部是 `frozen` dataclass**（`frozen=True, slots=True`）：按值相等、不可变、不可改字段。
2. **块级节点都带 `source_line`**：1 起的源文件行号，指向该块在 DFM 中的起始行。
3. **字段名与 Markdown 语法无关**：不出现 ``md``/``token``/``html`` 这类词。
4. **行内节点继承 `Inline`，块级节点继承 `Block`**；`InlineNode` / `BlockNode` 是联合类型别名。
5. **解析器不写视觉属性**：颜色、字号、字体只来自 config，IR 里只有语义
   （例如 `Styled(style_name="strong")` 而不是「加粗」）。

## 行内节点

| 节点 | 字段 | 说明 |
|---|---|---|
| `Text` | `content: str` | 纯文本（已按上下文需要转义） |
| `Styled` | `content: list[InlineNode]`, `style_name: str` | 样式作用域：`**粗体**`→`strong`、`*斜体*`→`em`、`~~删除~~`→`strike`、`[文字]{.关键字}`→`关键字`。`[inline]` 映射在**渲染/校验层**解析，IR 里始终是语义名 |
| `Code` | `content: str` | 行内代码 `` `x` ``，内部不再解析标记 |
| `Math` | `latex: str`, `display: bool = False` | 行内数学 `$x^2$`；LaTeX 原样保留 |
| `Link` | `url: str`, `content: list[InlineNode]` | `[文字](url)` |
| `Image` | `src: str`, `alt: str = ""` | 行内 `[[img:path]]` 或 `![alt](src)` |
| `Break` | — | 硬换行（行尾两空格或 `\`），或段落内的 `[[pagebreak]]` |
| `Ref` | `target: str` | `[[ref:目标]]` 交叉引用 → Word 的 `REF` 域 |
| `Footnote` | `text: str` | `[[fn:文字]]` 行内脚注 → 引用 run + `word/footnotes.xml` 条目 |

## 块级节点

| 节点 | 字段 | 对应语法 |
|---|---|---|
| `Heading` | `level: int`, `content: list[InlineNode]` | `#` ~ `######` |
| `Paragraph` | `content: list[InlineNode]` | 普通段落 |
| `ListBlock` | `ordered: bool`, `items: list[ListItem]` | `-`/`*`/`+` 与 `1.` |
| `ListItem` | `content: list[BlockNode]` | 列表项；嵌套列表就是 content 里再放一个 `ListBlock` |
| `CodeBlock` | `language: str`, `content: str` | ```` ```lang ````；`language` 为空串表示纯文本 |
| `Formula` | `latex: str`, `display: bool = True` | 独立成段的 `$$ … $$` |
| `ImageBlock` | `src: str`, `alt: str = ""`, `width: str = ""`, `align: str = ""` | 独立一行的 `[[img:path]]`（可带 `width=`/`align=`） |
| `ThematicBreak` | — | `---` |
| `PageBreak` | — | 独立一行的 `[[pagebreak]]` |
| `Toc` | — | `[[toc]]` → Word 的 `TOC` 域 |
| `NamedBlock` | `name: str`, `content: list[BlockNode]`, `attributes: dict[str, str]`, `label: str` | `\begin{名字 属性} … \end{名字}`；`label` 是 `#id`，供 `[[ref:...]]` 引用 |
| `BlockQuote` | `content: list[BlockNode]` | `>` |
| `Table` | `rows: list[list[str]]`, `cells: list[list[TableCell]]`, `alignments: list[str]`, `cell_nodes: list[list[list[InlineNode]]]` | `rows` 是纯文本视图；`cells`/`cell_nodes` 承载合并与行内格式（见下） |

`TableCell`（**不是** `Block`，无 `source_line`）：

| 字段 | 说明 |
|---|---|
| `blocks: list[BlockNode]` | 单元格内容（段落/列表/公式/图片），禁止嵌套表格 |
| `colspan` / `rowspan` | 合并跨度 |
| `is_merge_continuation` | 该格是被合并占用的位置 |
| `diag` / `diag_parts` | 斜线表头（对角线）信息 |

> `Table` 同时保留 `rows`（纯文本）与 `cells`/`cell_nodes`（结构化）：
> 前者让只关心文本的后端/测试简单读取，后者给 Word 后端做合并与行内格式。
> 改动表格逻辑时**两者都要维护**。

## 例子

```python
from docgen.parser.dfm import parse_dfm

parse_dfm("# 标题\n\n- 项\n")
```

```text
Heading(source_line=1, level=1, content=[Text(content='标题')])
ListBlock(source_line=3, ordered=False, items=[ListItem(source_line=3, content=[Paragraph(source_line=3, content=[Text(content='项')])])])
```

## 为什么这样设计

- **渲染层可替换**：第二题的 Word 渲染只要重新消费 IR，不需要改解析器。
- **可测试**：IR 是纯数据，快照测试直接比较对象，不做字符串比对。
- **行号可追溯**：错误能定位到源文件行列（`check --json` 的 `file:line:col`）。
- **稳定**：新增语法只新增节点或新增 `style_name`，不改已有字段。

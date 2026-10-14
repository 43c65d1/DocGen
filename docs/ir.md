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
| `Styled` | `content: list[InlineNode]`, `style_name: str` | 样式作用域：`**粗体**`→`strong`、`*斜体*`→`em`、`~~删除~~`→`strike`、`[文字]{.关键字}`→`关键字` |
| `Code` | `content: str` | 行内代码 `` `x` ``，内部不再解析标记 |
| `Math` | `latex: str`, `display: bool = False` | 行内数学 `$x^2$`；LaTeX 原样保留 |
| `Link` | `url: str`, `content: list[InlineNode]` | `[文字](url)` |
| `Image` | `src: str`, `alt: str = ""` | 行内 `[[img:path]]` 或 `![alt](src)` |
| `Break` | — | 硬换行（行尾两空格或 `\`），或段落内的 `[[pagebreak]]` |

## 块级节点

| 节点 | 字段 | 对应语法 |
|---|---|---|
| `Heading` | `level: int`, `content: list[InlineNode]` | `#` ~ `######` |
| `Paragraph` | `content: list[InlineNode]` | 普通段落 |
| `ListBlock` | `ordered: bool`, `items: list[ListItem]` | `-`/`*`/`+` 与 `1.` |
| `ListItem` | `content: list[BlockNode]` | 列表项；嵌套列表就是 content 里再放一个 `ListBlock` |
| `CodeBlock` | `language: str`, `content: str` | ```` ```lang ````；`language` 为空串表示纯文本 |
| `Formula` | `latex: str`, `display: bool = True` | 独立成段的 `$$ … $$` |
| `ImageBlock` | `src: str`, `alt: str = ""` | 独立一行的 `[[img:path]]` |
| `ThematicBreak` | — | `---` |
| `PageBreak` | — | 独立一行的 `[[pagebreak]]`（渲染为 `<hr class="pagebreak">`） |
| `BlockQuote` | `content: list[BlockNode]` | `>` |
| `Table` | `rows: list[list[str]]` | 简单表格；第一行是表头，单元格是纯文本 |

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

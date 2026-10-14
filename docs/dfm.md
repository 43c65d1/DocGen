# DFM 子集（剪枝版）

DFM = DocGen Flavored Markdown。剪枝版只实现手册 §5.1 的子集，
所有语法最终都变成 [IR](../src/docgen/ir.py) 节点；解析器不产生 HTML。

## 块级

| 语法 | IR 节点 |
|---|---|
| `#` ~ `######` 标题 | `Heading(level=1..6, content=[...], source_line=N)` |
| 普通段落 | `Paragraph(content=[...], source_line=N)` |
| `-` `*` `+` 无序列表 | `ListBlock(ordered=False, items=[ListItem(...)])` |
| `1.` `2.` 有序列表 | `ListBlock(ordered=True, items=[...])` |
| 列表嵌套（缩进 2 空格） | 子 `ListBlock` 放进父 `ListItem.content` |
| `>` 引用 | `BlockQuote(content=[块级节点...])` |
| ```` ```lang ```` 代码块 | `CodeBlock(language="lang", content="...")` |
| `---` 分隔线 | `ThematicBreak` |
| `\|a\|b\|` 简单表格 | `Table(rows=[["a", "b"], ...])`（第一行是表头） |
| 独立一行的 `[[img:path]]` | `ImageBlock(src="path")` |
| 独立一行的 `[[pagebreak]]` | `PageBreak()`（HTML 里渲染为 `<hr class="pagebreak">`） |
| 独立成段的 `$$ ... $$` | `Formula(latex="...")` |

## 行内

| 语法 | IR 节点 |
|---|---|
| `**粗体**` | `Styled(content=[...], style_name="strong")` |
| `*斜体*` | `Styled(content=[...], style_name="em")` |
| `~~删除~~` | `Styled(content=[...], style_name="strike")` |
| `` `code` `` | `Code(content="...")` |
| `[文字](url)` | `Link(url="url", content=[...])` |
| `[文字]{.样式名}` | `Styled(content=[...], style_name="样式名")` |
| `[[img:path]]`（行内） | `Image(src="path")` |
| `[[pagebreak]]`（行内） | `Break()` |
| `$x^2$` | `Math(latex="x^2", display=False)` |
| `H~2~O` | `Styled(content=[Text("2")], style_name="sub")` |
| `E=mc^2^` | `Styled(content=[Text("2")], style_name="sup")` |
| `[上标]{.sup}` / `[下标]{.sub}` | `Styled(style_name="sup"/"sub")` |
| 硬换行（行尾两空格或 `\`） | `Break()` |

上下标是 Pandoc 风格的单字符标记：内容不能含空白或换行，
`~~删除~~` 仍是删除线（双写留给 strikethrough），代码块与数学内不解析。

粗体 / 斜体 / 删除线也统一表达为 `Styled`，**视觉由 config 的样式表决定**，
解析器不写死任何颜色、字号或字体。

代码围栏的 `lang` 会原样记进 `CodeBlock.language`；允许的语言见下文「诊断」。
`$` 后紧跟数字或空白不当作数学（`价格 $5 元`、`$ $` 都是普通文本）。

## 双语法：fence 与 `\begin`（完整版 §6.2.5）

CommonMark 的 fence 长度规则对 LLM 不友好：内部含 ` ``` ` 或需要嵌套同类结构时，fence 会提前终止。
所以 DFM 提供第二套语法，在交给 markdown-it 之前处理：

````markdown
```python
print("hi")
```

\begin{code:python}
print("hi")          <!-- 内部可以再出现 ``` -->
\end{code:python}

\begin{caption #fig:1 .wide}
图 1 系统架构
\end{caption}
````

| 规则 | 说明 |
|---|---|
| `\begin{code:lang}` / `\end{code:lang}` | 与 fence 等价的代码块，**内容原样保留**（内部不解析任何标记） |
| `\begin{名字 属性}` / `\end{名字}` | 命名块容器（`caption`/`equation`/`abstract`…），内容按 DFM 继续解析、可嵌套 |
| 属性 | Pandoc 语法：`{.class #id key=value}` → `{"classes": ..., "id": ..., ...}` |
| 首尾名字 | 必须一致 → 否则 `E3002` |
| 独占一行 | `\begin` 必须独占一行；夹在段落中间报 `E4001` |
| 未闭合 | 缺 `\end` → `E3001` |
| 转义 | `\\begin` 是字面文本 |

**选择原则**：简单代码块用 fence；需要嵌套或内部含终止符时用 `\begin`。

## 冲突规则

1. 代码块（```lang … ```）内不解析任何标记。
2. 数学（`$...$`、`$$...$$`）内不解析 Markdown；LaTeX 原样保留（`\,`、`\frac` 不会被当转义吃掉）。
3. `[...]{...}` 的属性语法内不解析嵌套 `[...]`。
4. `\` 只转义后一个字符（`\*` → 字面 `*`）。

## 宽容解析 + 严格诊断

剪枝版把「解析」与「诊断」分成两层：

- **解析器永远宽容**：未闭合的标记退化为字面文本，不抛异常、不丢内容，
  所以 `docgen build` 任何时候都能产出结果。
- **`docgen check --strict` 负责报错**（普通 `check` 只报样式/图片这类语义错误）：

| 情况 | 输入示例 | 错误码 |
|---|---|---|
| 标记未闭合 | `[[img:a.png`、`[字]{.caption`、`$x^2 没闭合`、单独的 `$$`、未配对的 ` ``` ` | `E3001` |
| 代码围栏语言不在白名单 | ` ```rust ` → 允许；` ```cobol ` → 报错 | `E2001` |
| 代码围栏未配对（结构错误） | 只有一个 ` ``` ` | `E4001` |

语言白名单在 [`src/docgen/diagnostics.py`](../src/docgen/diagnostics.py) 的 `DEFAULT_LANGUAGES`
（python / markdown / bash / json / yaml / text 等 40 余个，含 `py`、`js` 这类别名；
空 info 一律允许）。扫描时跳过围栏、行内代码与块级公式内部的标记，
`\` 转义也不算未闭合。

静态类型等结构性错误（若将来引入）仍走 `E4001`。

| 输入（严格模式） | 结果 |
|---|---|
| `[[img:a.png` | `E3001:未闭合的标记: [[` @ 该行第 1 列 |
| `[[unknown]]` | 不是错误（合法标记 + 未知前缀会退化为字面文本） |
| `[文字]{.caption` | `E3001` |
| `价格是 $5 元` | 不是错误（`$` 后是数字） |
| `$$\nE = mc^2\n$$` | 不是错误（成对跨行） |

## 行号契约

每个块级节点的 `source_line` 是 **1 起的源文件行号**，指向该块在 DFM 中的起始行。
输入在解析前经过 `normalize_text`（去 BOM、统一 LF），所以行号与磁盘上的 LF 版本一致。

## 剪枝版不做

多级编号、题注、交叉引用、目录、脚注、复杂表格（合并/斜线表头）、数学渲染
（HTML 只占位或 MathJax）、`\begin{...}` 命名块、Word/OOXML —— 都留给第二题。

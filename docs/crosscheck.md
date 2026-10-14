# 金标准交叉验证

解析器是「两遍」实现的：`markdown-it-py` 从源文本产出 token 流，`parser/dfm.py` 再扫描
token 流变成 IR。**两遍扫描正是历史上出 bug 的地方**（嵌套列表被父列表吞掉、列表项内容
丢失）。

[`src/docgen/canonical.py`](../src/docgen/canonical.py) 用**一遍**扫描做独立对照：
同一个 token 流递归归约成规范结构，再与 IR 归约出的规范结构逐行比较。

```python
from docgen.canonical import compare_document
from docgen.parser.dfm import parse_dfm

diffs = compare_document(markdown, parse_dfm(markdown))  # [] 表示完全一致
```

## 比较什么

| 维度 | 规范形式 |
|---|---|
| 标题 | `h1 文本` ~ `h6 文本`（层级必须一致） |
| 段落 | `p 文本` |
| 列表 | `ul` / `ol`，每项一行 `li`，嵌套用两空格缩进 |
| 引用 | `blockquote` + 内容按层缩进 |
| 代码块 | `pre[language] 内容`（语言必须一致） |
| 表格 | `table` + 每行 `tr 单元格 \| 单元格` |
| 分隔线 / 分页 | `hr` |
| 块级公式 | `<math-display>` |
| 自研标记 | `[[...]]` → `<wiki>`（两边统一占位） |

文本比较前会折叠空白、剥掉行内标记（粗体/斜体/代码/链接），只比**内容**；
所以「行内标记如何嵌套」不影响结果，而「块结构与内容」必须完全一致。

## 为什么可信

- **独立性**：金标准侧不经过 `parser/dfm.py`，用一个 `for` 循环直接归约 token 流。
- **同一基座**：两边共用 markdown-it 的 CommonMark preset，所以差异只可能来自我们
  自己的扫描逻辑（正是要验证的部分）。
- **反向自检**：[`tests/test_crosscheck.py`](../tests/test_crosscheck.py) 里有两个用例
  故意喂错结构（标题层级写错、嵌套列表被拍平、语言写错），确认比较器**能报出差异**，
  而不是永远返回空列表。
- **夹具全量**：`tests/fixtures/full.md`（覆盖所有节点类型）也要逐行一致。

## 已知的口径差异（都已归一）

| 情况 | 金标准侧 | 产品侧 | 归一方式 |
|---|---|---|---|
| `$$ … $$` | 段落里的数学 token | `Formula` 块 | 两边都归约成 `<math-display>` |
| 独立一行 `[[img:]]` | 段落文本 | `ImageBlock` | 两边都归约成 `<wiki>` |
| 独立一行 `[[pagebreak]]` | 段落文本 | `PageBreak` | 两边都归约成 `hr` |
| `[x]{.style}` | 字面文本 | `Styled` | 金标准剥掉属性语法 |

另外 markdown-it 的行内规则有一条「文本里没有特殊字符就跳过全部规则」的快速路径，
`$` 与 `[` 都不在默认 `specialChars` 里；金标准解析器显式把它们加上，规则才会被调用。

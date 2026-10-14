# DocGen 特性矩阵

这份文档的**每一行都在验证一个具体特性**，且每个特性都带一个「信号值」——
肉眼可辨、机器可断言。任何一项失效都能立刻看出来，不必反查 OOXML。

配套命令：

```bash
docgen check examples/features/content.md -c examples/features/config.toml --strict
docgen build examples/features/content.md -c examples/features/config.toml -o examples/features/output.docx
docgen build examples/features/content.md -c examples/features/config.toml -o examples/features/output.html
```

## 行内格式（每行一个特性）

- **feature-bold** —— 加粗。机器信号：`<w:b/>`
- *feature-italic* —— 斜体。机器信号：`<w:i/>`
- ~~feature-strike~~ —— 删除线。机器信号：`<w:strike/>`
- [feature-underline]{.feature_underline} —— 下划线。机器信号：`<w:u w:val="single"/>`
- [feature-color]{.feature_color} —— 红字。机器信号：`<w:color w:val="C00000"/>`
- [feature-small]{.feature_small} —— 明显偏小。机器信号：`<w:sz w:val="16"/>`（8pt）
- `feature-code` —— 等宽字体。机器信号：等宽 `w:ascii="Consolas"`
- H~2~O —— 下标 2。机器信号：`w:vertAlign w:val="subscript"`
- E=mc^2^ —— 上标 2。机器信号：`w:vertAlign w:val="superscript"`
- [feature-link](https://example.com/feature) —— 蓝色可点击。
  机器信号：`<w:hyperlink r:id="…">` + rels 里 `TargetMode="External"`
- $a^2+b^2=c^2$ —— 行内公式。机器信号：`<m:oMath>`

混排一行（同一段里全部生效）：**粗** *斜* ~~删~~ [下划线]{.feature_underline}
[红字]{.feature_color} [小字]{.feature_small} `code` H~2~O CO~2~ $x^2$
[链接](https://example.com/mix)。

说明：`**粗**` 走的是**内置样式名** `strong`（`*斜*`→`em`、`~~删~~`→`strike`、
`H~2~O`→`sub`、`E=mc^2^`→`sup`）。config 必须声明 `[styles.strong]` 这类名字，
光写自定义名（如 `[styles.feature_bold]`）不会让 Markdown 语法变粗。

## 自定义样式（信号色）

[关键字样式]{.keyword}是蓝色加粗；这句里没有样式的部分是默认排版。

## 列表

- 无序项一
- 无序项二
  - 嵌套项（缩进两个空格）
1. 有序项一
2. 有序项二

## 代码块（语言变体换色）

Python 块应是**绿色**、JavaScript 块应是**暗金色**，两者都保留基座的
Consolas 9pt 与浅灰底纹——这同时验证了「深合并」是否正确。

```python
def feature_python() -> str:
    return "python 块 → 绿色 008000"
```

```javascript
function featureJavascript() {
  return "javascript 块 → 暗金 B8860B";
}
```

```text
纯文本块 → 不给语言变体色，只有基座的灰底 + 等宽字体
```

## 引用与分隔线

> 引用第一段。
>
> 引用第二段。

上面与下面之间是 `---` 分隔线——它应该是**一条横贯正文的线**（段落底边框），
不是一长串破折号字符。线段样式由 `[document] hr.style` 控制。

---

被分隔线隔开的下文。

## 标题编号开关

本节的编号（`1.4` 之类）**不是写在标题文字里的**，而是由 Word 的编号域生成，
来自 `[document] heading_numbering`（默认开启）：

```toml
[document]
heading_numbering = true    # 默认；H1 → "1"、H2 → "1.1"
# heading_numbering = false # 关掉：标题就不再自动编号
```

> ⚠️ 如果标题文字本身就以数字开头（如 `# 1 概述`），会叠加成 `1 1 概述` /
> `1.1 1 概述` 这种观感。这时要么改标题文字，要么关掉 `heading_numbering`。
> 关掉后 `outlineLvl` 仍在，**目录与导航窗格照常工作**。

## 表格：两种边框样式对照

**先说结论**：默认 `[table] style = "three_line"`，它**就是**
「只有顶线、表头下线、底线，**没有竖线**」——学术三线表，**设计如此，不是缺陷**。
想要竖线就把 style 改成 `grid`。

### 三线表（默认，无竖线）

| 单元格语法 | 期望渲染 | 数学 |
| --- | --- | --- |
| **粗体** | 加粗，不是字面两星号 | $x^2$ |
| *斜体* | 倾斜 | $y_1$ |
| `code` | 等宽 | $z=0$ |
| [链接](https://example.com/cell) | 可点击 | $\frac{1}{2}$ |

### 三种样式

| `[table] style` | 框线外观 |
| --- | --- |
| `three_line`（默认） | 顶线 + 表头下线 + 底线，**无竖线** |
| `grid` | 四周框线 + 全部内部横竖线 |
| `none` | 完全无框线 |

把配置改成 `style = "grid"` 重跑，同一张表就会画出竖线。

## 块级公式与编号

$$
\int_0^1 x \, dx = \frac{1}{2}
$$

带编号的公式（无边框三列表格，编号可被引用）：

\begin{equation #eq:feature number=1}
$$
E = mc^2
$$
\end{equation}

## 题注与交叉引用

\begin{caption #fig:feature}
特性矩阵示意（题注编号应由 Word 的 SEQ 域生成）
\end{caption}
见图 [[ref:fig:feature]]，另见式 [[ref:eq:feature]]。

## 脚注

正文里带脚注[[fn:这是脚注文本，应出现在页面底部并自动编号]]，再来一个[[fn:第二条脚注]]。

## 图片与分页

[[img:pics/photo.png width=3cm align=center]]

[[pagebreak]]

最后一页：验证分页符、页眉「DocGen 特性矩阵」与页脚「第 N 页」。

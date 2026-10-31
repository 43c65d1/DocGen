# 语义手册：每种排版元素 → 默认效果 → 怎么改

> **日常查字段先用 [cheatsheet.md](cheatsheet.md)（一页速查）**；本文是细节版：
> 讲默认值从哪来、覆盖层级、边界情况。配置完整语法见
> [config.md](config.md)，Word/OOXML 细节见 [word.md](word.md)，语法见 [dfm.md](dfm.md)。

## 0. 先理解三件事

1. **config 是唯一真源**：除「母版自带样式」外，引擎不写死视觉属性。
   例如 `[styles.strong]` 不声明，`**粗体**` 就**不会加粗**（内容照常输出）。
2. **默认值来自母版**（python-docx 自带模板），下文的数值是**实测的模板值**，
   不是引擎硬编码。改 config 会覆盖它们。
3. **「默认效果」一列写的是「不写任何 config」时的样子**；「字段」一列是
   config 里的**精确键名**，格式为 `[段名] 键`。

默认页面（未配 `[[sections]]` 时）：**Letter 21.59×27.94cm**，
页边距 上下 2.54cm / 左右 3.17cm。

---

## 1. 文档级：`[document]`

| 字段 | 默认效果 | 说明 |
|---|---|---|
| `font.name` | 主题字体（西文 minorHAnsi / 中文 minorEastAsia） | 写入 `Normal`，正文继承 |
| `font.size` | 11pt | 同上 |
| `font.east_asia` | 无 | 代码块里中文的回退字体（可选） |
| `line_spacing` | 1.15 倍（276/240） | 正文行距；`1.5` / `"20pt"` 这类数值按倍数 |
| `heading_numbering` | **开** | 标题多级编号；`false` 关闭 |
| `heading_indent` | 母版缩进（`left=720` + `hanging=360`） | 三种写法：`false` / 表 / 数字，见 §2 |
| `alignment` | 无（继承） | 段落对齐，会被 `[styles.*]` 覆盖，见 §3 |
| `space_before` / `space_after` | 无 | 段前/段后，见 §3 |
| `hr.style` / `hr.color` / `hr.size` | `single` / `auto` / `6`（0.75pt） | `---` 分隔线的线型/颜色/粗细 |

> `font.*` 是点号键，展开后是嵌套表。`[document] font.name = "宋体"` 与
> `[document.font] name = "宋体"` 等价。

## 2. 标题：`[styles.heading1]` … `[styles.heading9]`

不写 config 时的母版值：

| 样式 | 字号 | 加粗 | 颜色 | 段前 | 缩进 |
|---|---|---|---|---|---|
| `heading1` | 14pt | 是 | 主题蓝 `365F91` | 24pt | `left 720` + `hanging 360` |
| `heading2` | 13pt | 是 | 主题蓝 `4F81BD` | 10pt | 同上 |
| `heading3` | 11pt（继承） | 是 | `4F81BD` | 10pt | 同上 |
| `heading4`–`heading9` | 11pt（继承） | 4 是 / 5–6 否 | `4F81BD` / `243F60` | 10pt | 同上 |

可用字段：`font.name` / `font.size` / `font.bold` / `font.italic` / `font.color` /
`font.underline` / `font.strike` / `alignment` / `space_before` / `space_after`。

- **编号**：`[document] heading_numbering = false` 关闭；缩进用 `heading_indent`。
- `heading_indent` 的三种写法：

  ```toml
  heading_indent = false              # 全部取消缩进
  heading_indent = 0                  # 所有级别都不缩进
  [document.heading_indent]           # 分级别
  "1" = { left = 0, hanging = 0 }
  "2" = { left = 420, hanging = 0 }
  ```

- 标题只吃「对齐 + 段距」，**不会**继承正文的行距与首行缩进。
- 标题的 `font.*` 同时写进 **run** 和 `Heading N` **样式定义**（否则 Word 里
  「新敲一个标题」会回到母版主题蓝）。

## 3. 正文段落：`[styles.body]`、对齐与间距

正文段落默认：**主题字体 11pt、段后 10pt、1.15 倍行距、无首行缩进、左对齐**。

| 字段 | 默认效果 | 说明 |
|---|---|---|
| `font.*` | 继承 `[document]` | 写进 `Normal` 样式 |
| `line_spacing` | 继承 `[document]` | 段后/段前见下 |
| `first_line_chars` | 无（0） | 首行缩进，单位是**字符**：`200` = 2 字符 |
| `alignment` | 无（继承） | `left` / `right` / `center` / `justify`(=both) |
| `space_before` / `space_after` | 无 | 见下 |

对齐与段距的**层级**：`[document]` 兜底 → `[styles.body]` / `[styles.headingN]` /
`[styles.caption]` 覆盖。只设 `[document] alignment` 时标题也会跟着对齐。

段前/段后的单位：

| 写法 | 产出 | 说明 |
|---|---|---|
| `"6pt"` / `"12px"` / `"0.2cm"` / `6` | `w:before` / `w:after` | 1pt = 20 twips；裸数字按磅 |
| `"0.5 line"` / `"1行"` | `w:beforeLines` / `w:afterLines` | 百分之一行（0.5 行 = 50） |

写错单位会报 `E5001`（不再静默丢弃）。

**逐段覆盖**：`[文字]{.样式名}` 的样式里可写 `alignment` / `first_line_chars` /
`space_before` / `space_after`，作用于**所在段落**——封面署名这类需求就靠它：

```toml
[styles.signature]
first_line_chars = 0
alignment = "center"
```

```markdown
[学号：5120242907　姓名：官畅宇　班级：软件2406]{.signature}
```

## 4. 行内语义：`strong` / `em` / `strike` / `sup` / `sub` / 链接 / 代码

| 语法 | 语义名 | 不写 config 时 | 字段 |
|---|---|---|---|
| `**粗体**` | `strong` | **不加粗**（内容照常） | `[styles.strong] font.bold = true` |
| `*斜体*` | `em` | 不倾斜 | `[styles.em] font.italic = true` |
| `~~删除~~` | `strike` | 不删除线 | `[styles.strike] font.strike = true` |
| `^上标^` / `[字]{.sup}` | `sup` | 上标（语义固定） | 字号可配 `[styles.sup] font.size` |
| `~下标~` / `[字]{.sub}` | `sub` | 下标（语义固定） | 同上 |
| `[字]{.任意名}` | 该名字 | 无格式 | `[styles.任意名]` 任意字体键 |
| `` `code` `` | 行内代码 | Consolas + 底纹 `F2F2F2` | `[code_block] font.name` / `inline_background` |
| `[文字](url)` | 超链接 | 蓝色 `0563C1` + 下划线 | 颜色固定（Word 惯例） |

**改名映射**：`[inline] sup = "sup_caret"` 让 `^x^` 去找 `[styles.sup_caret]`。
映射目标必须声明，否则报 `E1003`（错误里会打出整条映射链）。

## 5. 列表

| 语法 | 默认效果 | 字段 |
|---|---|---|
| `- 项` | Word 内置 `List Bullet`（缩进按样式） | 无专用键；`[styles.*]` 不作用于内置列表样式 |
| `1. 项` | Word 内置 `List Number`，**每个列表独立从 1 开始** | 无 |

- 多级列表用缩进：`- 项` 下再缩进 2 空格 → 层级 +1（上层样式 `List Bullet 2/3`）。
- 有序列表的「独立计数」是渲染时给每个列表分配独立 `w:num` 实现的；
  嵌套有序列表同样各自从 1 开始。
- 列表段落的字体/缩进目前来自 Word 内置样式，**没有**逐级 config 键。

## 6. 代码块：`[code_block]` / `[code_block.<语言>]`

| 项 | 默认效果 | 字段 |
|---|---|---|
| 字体 | Consolas（中文回退走样式链） | `font.name` / `font.size` / `font.color` / `font.bold` 等 |
| 行距 | 固定 1.0 | 不可配 |
| 背景 | 无 | `background = "F5F5F5"` |
| 外框 | 无 | `border = "CCCCCC"` |
| 语言变体 | 按围栏语言名匹配 | `[code_block.python]` 覆盖 base |
| 行内代码底纹 | 默认 `F2F2F2` | `inline_background`（空串 = 不画） |

`[code_block]` 与 `[code_block.<lang>]` **深合并**（变体只覆盖同名字段）。

## 7. 表格：`[table]`

默认（不写 `[table]`）：**三线表** + 表头加粗 + 跨页重复表头 + 列宽均分正文宽度。

| 字段 | 默认 | 说明 |
|---|---|---|
| `style` | `three_line` | `three_line` / `grid` / `none` / `custom` |
| `header_repeat` | `true` | 跨页时表头重复 |
| `col_widths` | 均分 | 相对比例数组，如 `[3, 2, 5]` |
| `line_style` | `single` | 线型：`single` / `double` / `dashed` / `dotted` / `none` |
| `line_size` | 母版默认（表头线 1pt） | 线宽：`"1pt"` / `"0.5pt"` / `"8px"`（1/8 磅换算） |
| `line_color` | `auto`（黑） | 线色：`"000000"` / `"999999"` / `"auto"` |
| `edges` | 无 | **逐边**线型，仅 `style = "custom"` 时生效 |
| `row_lines` | `false` | 每行（除最后一行）底部加横线；`true` 或线型字符串 |
| `space_before` / `space_after` | 无 | 表格与上下文的间距（写到相邻段落） |

**逐边线型**（`custom`）：

```toml
[table]
style = "custom"
line_size = "1pt"
line_color = "000000"
edges = { top = "single", bottom = "single", left = "none", right = "none", insideH = "single", insideV = "none" }
```

可用的边：`top` / `left` / `bottom` / `right` / `insideH` / `insideV`。
未写的边默认 `none`；写错边名报 `E5001`。

**行间横线**（模拟「每行一条分隔线」）：

```toml
[table]
style = "none"
row_lines = true          # 或 row_lines = "dashed"
```

**斜线表头**：在单元格里写 `[[diag:右上;左下]]`（**分隔符用 `;`**，
不能用 `|`——那是表格单元格分隔符）：

```markdown
| [[diag:年份;项目]] | 2024 | 2025 |
| --- | --- | --- |
| A | 1 | 2 |
```

效果：该单元格加一条左上→右下的斜线（`w:tcBorders/tl2br`，线宽/颜色同上），
「年份」右对齐、「项目」左对齐，分两段。

**表格与正文间距**：Word 表格没有「表格前/后间距」属性，所以：

| 配置 | 实际写到 | 效果 |
|---|---|---|
| `[table] space_before` | 表格**前**一段的段后距 | 表格与上文隔开 |
| `[table] space_after` | 表格**后**一段的段前距 | 表格与下文隔开 |

**不支持**：行高（`trHeight`）、列宽按厘米（只有相对比例）、逐单元格边框
（斜线除外）、单元格内多段落（GFM 单元格只有行内内容）、合并单元格的
DFM 语法（IR 支持 `colspan/rowspan`，但解析器不产生）。

## 8. 图片：`[image]`

| 字段 | 默认 | 说明 |
|---|---|---|
| `width` | 图片原始尺寸 | `"4cm"` / `"120px"` / `"2in"` |
| `align` | 无（左对齐） | `left` / `center` / `right` |
| `space_before` / `space_after` | 无 | 图片段落的段前/段后 |

单张图片可覆盖默认：`[[img:pics/a.png width=3cm align=center]]`。

图片后**紧跟图题**时：图片段落自动 `keepNext`（不会图题跑到下一页）、
图题段落 `keepLines`（图题不被拆开）。图题默认居中。

## 9. 题注 / 交叉引用 / 目录 / 公式 / 脚注

| 语法 | 默认效果 | 相关字段 |
|---|---|---|
| `\begin{caption #fig:1}` | 题注段落（`Caption` 样式：跟正文同字体、**居中**）+ `SEQ 图` 域自动编号 | `[styles.caption] font.*` / `alignment` / `space_*` |
| `\begin{table #tab:1}` | 同上，前缀「表」 | 同上 |
| `\begin{equation #eq:1 number=1}` | 无框三列表格：左空 / 公式居中 / 右编号 `(1)`，编号带书签 | 编号值由作者给 |
| `[[ref:fig:1]]` | `REF` 域，显示目标编号 | 无 |
| `[[toc]]` | `TOC` 域（Word 打开时填充） | 无 |
| `[[fn:文字]]` | 脚注，编号由 Word 自动生成；`FootnoteText` 单倍行距 | `[styles.footnote] line_spacing`（倍数） |

- 域缓存值**已烘焙**：`SEQ` / `REF` 写的是真实编号，WPS/预览也能看到正确编号；
  `PAGE` / `TOC` 仍需查看器更新（分页相关）。
- 题注编号按类型独立计数（图 1、图 2、表 1…）。

## 10. 公式：`[math]`

| 字段 | 默认 | 说明 |
|---|---|---|
| `engine` | `auto` | `auto` / `xsl` / `plain` |
| `on_fail` | `plain` | 转换失败时降级为 LaTeX 文本；`error` 则报 `E5002` |
| `xsl` | 自动查找 | `MML2OMML.XSL` 路径；也可用环境变量 `DOCGEN_MML2OMML` |

行内公式 `$x^2$` 与块级 `$$…$$` 都转 OMML（Word 里可编辑）。
没有 XSL（如 Linux CI）时降级为文本，不中断构建。

## 11. 分节 / 页码 / 页眉页脚 / 封面：`[[sections]]`

不写 `[[sections]]`：单节，页面/页边距取母版（Letter、2.54/3.17cm），无页眉页脚、无页码。

写了之后，每条配置描述一节（**第一条作用于现有节，其余靠 `[[sectionbreak]]` 新建**）：

| 字段 | 默认 | 说明 |
|---|---|---|
| `page.size` | `A4` | `A4` / `A3` / `A5` / `Letter` / `Legal` |
| `page.width` / `page.height` | — | 自定义尺寸（cm），覆盖 size |
| `page.margin.top/bottom/left/right` | 母版 | 单位 cm |
| `numbering.format` | 无 | `decimal` / `upperRoman` / `lowerRoman` / `upperLetter` / `lowerLetter` |
| `numbering.start` | 无 | 重启页码（1 起） |
| `header.text` / `footer.text` | 无 | 页眉/页脚文字；`PAGE` 变成页码域 |
| `cover` | `false` | `true` = 该节页面垂直居中（不是"生成封面内容"） |

正文里用 `[[sectionbreak]]` 切到下一节；不写标记时内容全部落在最后一节
（旧行为，前面各节是空页）。详见 [word.md](word.md) 的「分节」一节。

## 12. 输出与日志：`[output]`

| 字段 | 默认 | 说明 |
|---|---|---|
| `level` | `warn` | 终端阈值：`log` / `warn` / `err` / `none` |
| `logfile` | 无 | 日志文件路径（相对路径按当前工作目录） |
| `logfile_level` | `log` | 文件阈值，独立于终端 |

命令行 `-q` / `-v` / `--logfile` 覆盖它们；`level = "none"` 只静默打印，**退出码照常**。

## 13. 错误码

| 码 | 含义 |
|---|---|
| `E1001` | 循环继承（`based_on` 成环） |
| `E1002` | 继承深度超限 |
| `E1003` | 引用不存在的样式 / `[inline]` 映射目标缺失 |
| `E2001` | 未知语言（代码块语言变体） |
| `E2010` | `keywords` 值非法 |
| `E3001` | 标记未闭合（含 `\begin` 未闭合） |
| `E3002` | `\begin` 与 `\end` 名字不一致 |
| `E4001` | 语法错误（含标签重复） |
| `E5001` | config / 母版缺失或版本不符（含非法键值） |
| `E5002` | 数学转换失败 |
| `E5003` | 分节配置错误 |
| `E5004` | 编号 / 交叉引用目标不存在 |

`docgen check --strict` 会把 `E3001` / `E2001` / `E4001` 一并报出。

---

## 14. 常见任务配方

**把标题改成黑体、正文改宋体 12pt**

```toml
[document]
font.name = "宋体"
font.size = "12pt"

[styles.heading1]
font.name = "黑体"
font.size = "18pt"
```

**正文首行缩进 2 字符，但署名行不缩进**

```toml
[styles.body]
first_line_chars = 200

[styles.signature]
first_line_chars = 0
alignment = "center"
```
```markdown
[学号：… 姓名：…]{.signature}
```

**表格用 1pt 黑框、行间横线**

```toml
[table]
style = "custom"
line_size = "1pt"
line_color = "000000"
row_lines = true
edges = { top = "single", bottom = "single", left = "single", right = "single", insideV = "none" }
```

**给表格加斜线表头**

```markdown
| [[diag:年份;项目]] | 2024 | 2025 |
| --- | --- | --- |
| A | 1 | 2 |
```

**图题与图片一起换页、题注红色**

```toml
[styles.caption]
font.color = "404040"
```
（图题自动与图片同页；颜色/字号由 `[styles.caption]` 控制）

**封面单独一页、罗马页码**

```toml
[[sections]]
page.size = "A4"
numbering.format = "upperRoman"
cover = true

[[sections]]
page.size = "A4"
numbering.format = "decimal"
numbering.start = 1
footer.text = "第 PAGE 页"
```
```markdown
# 报告标题

[[sectionbreak]]

# 一、正文
```

**段前留一行、段后 6pt**

```toml
[styles.body]
space_before = "1 line"
space_after = "6pt"
```

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

> **输入编码**：DFM / config / 文献库统一按「UTF-8（含 BOM）优先，GB18030 兜底」
> 读取（best effort，兼容 Windows 记事本存的 GBK/GB2312）；其它编码报 `E5001`。
> 产物 `.docx` 始终是 UTF-8。

---

## 1. 文档级：`[document]`

| 字段 | 默认效果 | 说明 |
|---|---|---|
| `font.name` | 主题字体（西文 minorHAnsi / 中文 minorEastAsia） | 中文字体；只写它时西文也用它 |
| `font.latin` | 无（跟随 `font.name`） | **西文字体**（ascii/hAnsi/cs）；写它就只换西文，中文仍用 `font.name` |
| `font.size` | 11pt | 字号：`12pt` / `1.5em` / `16px`，或**中文字号**（`小四` / `三号`） |
| `font.east_asia` | 无 | 代码块里中文的回退字体（可选） |
| `line_spacing` | 1.15 倍（276/240） | 正文行距：数字 = **倍数**（`1.5`）；带 `pt`/`磅` = **固定磅值**（`"20pt"` → `w:lineRule="exact"`） |
| `heading_numbering` | **开**（decimal） | 标题编号：`false` 关闭；`decimal` / `chapter`（第一章）/ `chinese`（一、） |
| `caption_numbering` | `continuous` | 图/表编号：`chapter` = 按章编号（图 2-1） |
| `heading_indent` | 母版缩进（`left=720` + `hanging=360`） | 三种写法：`false` / 表 / 数字，见 §2 |
| `alignment` | 无（继承） | 段落对齐，会被 `[styles.*]` 覆盖，见 §3 |
| `space_before` / `space_after` | 无 | 段前/段后，见 §3 |
| `hr.style` / `hr.color` / `hr.size` | `single` / `auto` / `6`（0.75pt） | `---` 分隔线的线型/颜色/粗细 |
| `east_asia_lang` | `zh-CN` | 避头尾用哪套禁则表（`zh-TW` / `ja-JP` / `ko-KR`） |
| `kinsoku` / `overflow_punct` | 开 / 开 | 行首尾禁则、行尾标点溢出边界 |
| `compress_punctuation` | 开 | 标点压缩（优先挤回上一行） |
| `auto_space` | 开 | 中西文/中文与数字自动留白 |

> **避头尾**：引擎默认写 `docDefaults/eastAsia="zh-CN"` 并打开上述开关，
> 标点不会落到行首。实测：模板原样（`en-US` + `doNotCompress`）有 2 处行首标点，
> 改成 `zh-CN` 后 0 处——**语言标记才是决定性因素**，只写 `kinsoku` 不够。
> 细节与实测表见 [word.md](word.md) 的「避头尾」一节。

> `font.*` 是点号键，展开后是嵌套表。`[document] font.name = "宋体"` 与
> `[document.font] name = "宋体"` 等价。

> **中文字号（号数制）**：`font.size = "小四"` 会换算成 12pt（Word/WPS 同口径）。
> 常用换算：初号 42 / 小初 36 / 一号 26 / 小一 24 / 二号 22 / 小二 18 /
> 三号 16 / 小三 15 / 四号 14 / 小四 12 / 五号 10.5 / 小五 9 /
> 六号 7.5 / 小六 6.5 / 七号 5.5 / 八号 5（单位 pt）；写「小四号」也认。
> 严格印刷标准按毫米定义号数，与这套软件口径差异 <1%，文档排版可忽略。

## 2. 标题：`[styles.heading1]` … `[styles.heading9]`

不写 config 时的母版值：

| 样式 | 字号 | 加粗 | 颜色 | 段前 | 缩进 |
|---|---|---|---|---|---|
| `heading1` | 14pt | 是 | 主题蓝 `365F91` | 24pt | `left 720` + `hanging 360` |
| `heading2` | 13pt | 是 | 主题蓝 `4F81BD` | 10pt | 同上 |
| `heading3` | 11pt（继承） | 是 | `4F81BD` | 10pt | 同上 |
| `heading4`–`heading9` | 11pt（继承） | 4 是 / 5–6 否 | `4F81BD` / `243F60` | 10pt | 同上 |

可用字段：`font.name` / `font.latin` / `font.size` / `font.bold` / `font.italic` / `font.color` /
`font.underline` / `font.strike` / `alignment` / `space_before` / `space_after`。

> `font.size` 同样接受中文字号（`三号` / `小四` …），换算表见 §1。

- **编号**：`[document] heading_numbering = false` 关闭；缩进用 `heading_indent`。
- **编号格式预设**（`chapter` / `chinese` 为构建期烘焙文本，TOC 里同样显示）：

  ```toml
  [document]
  heading_numbering = "chapter"   # 第一章 / 1.1 / 1.1.1
  # heading_numbering = "chinese" # 一、 / （一） / 1. / （1）
  # heading_numbering = "decimal" # 1 / 1.1 / 1.1.1（默认，Word 多级编号）
  ```

  `chapter` 只影响一级标题的显示（第一章），二级/三级仍用阿拉伯章号（1.1 / 1.1.1）；
  `chinese` 的一级为「一、」、二级「（一）」、三级「1.」、四级「（1）」。
  切换后标题样式不再挂 Word 自动编号（避免「1 第一章」双重编号），
  改动后重建即可。
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
| `[文字](url)` | 超链接 | 蓝色 `0563C1` + 下划线 | `[styles.hyperlink]` 可改颜色/去下划线（支持 `font.color` / `underline`） |

超链接默认 Word 蓝 + 单下划线；要全文纯黑：`[styles.hyperlink] font.color = "000000"`、
`underline = "none"`（不能写 `false`——样式层把 `false` 当删除继承键）。

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

默认（不写 `[table]`）：**三线表** + 表头加粗 + 跨页重复表头 + 列宽均分正文宽度；
**表头与首行数据同页**（表头不孤行）。三线表线宽按学术规范：
**顶/底线 1.5pt（粗）、栏目线 0.5pt（细）**，两者必须有区分。

| 字段 | 默认 | 说明 |
|---|---|---|
| `style` | `three_line` | `three_line` / `grid` / `none` / `custom` |
| `header_repeat` | `true` | 跨页时表头重复 |
| `header_keep_with_body` | `true` | 表头与首行同页：表头段落 `keepNext` + 表头行 `cantSplit`。关掉会出现「表头单独留在页底」的排版缺陷 |
| `rows_keep_together` | `true` | 所有表格行 `cantSplit`，行内不跨页；`false` 允许长行拆到两页 |
| `col_widths` | 均分 | 相对比例 `[3, 2, 5]`、绝对宽度 `["3cm", "5cm"]`，或 `"auto"` 按内容估算；列表可混绝对宽度 + `"auto"` |
| `autofit` | `false` | `true` = 列宽交给 **Word autofit**；与 `col_widths` 互斥（同时写报 `E5001`） |
| `row_height` / `header_row_height` | 无 | 行高（如 `"0.8cm"` / `"20pt"`）；表头可单独设 |
| `row_height_rule` | `atLeast` | `atLeast` / `exact` / `auto` |
| `cell_vertical_align` | 无（Word 默认 top） | 单元格垂直对齐：`top` / `center` / `bottom` |
| `cell_margin` | 无（Word 默认：左右 0.19cm、上下 0） | 单元格内边距，四边统一，如 `"0.1cm"` |
| `cell_margin_top/bottom/left/right` | 无 | 逐边覆盖 `cell_margin`（单位必须写 cm/pt） |
| `line_style` | `single` | 线型：`single` / `double` / `dashed` / `dotted` / `none` |
| `outer_line_size` | `1.5pt` | 顶线/底线（粗线） |
| `header_line_size` | `0.5pt` | 栏目线（表头下，细线） |
| `aux_line_size` | 同栏目线 | 辅助线（`[[aux]]`，合计行上方） |
| `header_line` | `true` | `false` = **二线表**（只有顶线 + 底线） |
| `line_size` | 无 | **统一线宽**（旧行为）：设了它三线表三条线都用该值 |
| `line_color` | `auto`（黑） | 线色：`"000000"` / `"999999"` / `"auto"` |
| `edges` | 无 | **逐边**线型，仅 `style = "custom"` 时生效 |
| `row_lines` | `false` | 每行（除最后一行）底部加横线；`true` 或线型字符串 |
| `decimal_align` | 无 | 数值列（1 起列号，如 `[2, 4]`）：小数点/个位对齐；只处理纯数字，表头不参与 |
| `space_before` / `space_after` | 无 | 表格与上下文的间距（写到相邻段落） |
| `header_bold` | `true` | 表头加粗开关（`false` = 表头与正文同粗） |
| `[table.text]` | 无 | 单元格文字格式（见下）：`font.*` / `line_spacing` / `space_before` / `space_after` |

**Word autofit**：`autofit = true` 写 `tblLayout autofit` + `tblW auto`，列宽由查看器
按内容计算。优点是简单、贴近 Word 行为；缺点是 **Word/WPS/LibreOffice 结果可能不同**，
排版不可复现。需要确定性时用默认的构建期宽度（`col_widths` / `"auto"`）。

**自动列宽**：`col_widths = "auto"` 按单元格内容估算（CJK 记 2、ASCII 记 1），
短列自动变窄；也可 `["3cm", "auto"]` 固定第一列、其余按内容分剩余宽度。
这是**构建期**计算，结果确定，不依赖 Word/WPS 的 autofit 差异。

**单行行高**：在任意单元格写 `[[row-height:1.2cm]]`，只作用于该行；标记不渲染文字。
全局/表头仍用 `row_height` / `header_row_height`。

**逐单元格边框**：在单元格里写标记，给该格单独加边框（标记不渲染文字）：

```markdown
| 项目 | 数值 |
| --- | --- |
| [[border:all style=double size=1.5pt color=FF0000]] 重点 | 10 |
| 普通 | [[border:top,bottom]] 20 |
```

边名：`all` 或 `top,left,bottom,right` 组合；`style` 支持
`single/double/dashed/dotted/none`；`size` 如 `1.5pt`；`color` 6 位十六进制或 `auto`。
非法边名/线型/颜色/尺寸报 `E5001`。

表题写在表格**上方**且标 `kind=table` 时，题注段自动 `keepNext`，与表格同页；
表格行默认全部 `cantSplit`（行内不跨页，`rows_keep_together = false` 可关）。

**单元格文字与行距**（`[table.text]`）：表格单元格默认继承 `Normal`
（与正文段落是两条路径），需要更紧凑时显式配置：

```toml
[table.text]
line_spacing = 1.0        # 行距倍数（同 [styles.*] 的 line_spacing）
space_before = "0pt"      # 单元格段落段前
space_after = "0pt"       # 段后
font.size = "9pt"         # 字体类字段与 [styles.*] 相同：name/size/color/bold/italic
font.name = "黑体"
```

- 只写**显式配置**的键；不写就保持原样（继承 `Normal`）。字体字段与样式一致，
  支持 `font.name`（中文）+ `font.latin`（西文）分开设置。
  `font.size` 也接受中文字号（`五号` / `小五` …）。
- `header_bold` 是根级开关；`[table.text] font.bold` 显式写了则以它为准。
- 行距与样式一致：数字 = 倍数（`1.0` / `1.5`）；`"18pt"` / `"18磅"` = 固定磅值。

**辅助线**：合计 / 小计 / 统计处理结果行上方常需一条辅助线，在该行任一单元格写
`[[aux]]`（标记不渲染文字）：

```markdown
| 项目 | 金额 |
| --- | --- |
| A | 10 |
| [[aux]] 合计 | 10 |
```

**二线表**：横向阅读逻辑的表格更适合二线表（`header_line = false`），
强行套三线表反而破坏可读性。

**合并单元格**：在单元格开头写 `[[merge:列数]]`（横并）或 `[[merge:列数,行数]]`（横并 + 纵并）：

```markdown
| 项目 | 说明 [[merge:2]] | |
| --- | --- | --- |
| 合并 [[merge:1,2]] | B | C |
| | D | E |
```

- `[[merge:2]]` = 横跨 2 列；`[[merge:1,2]]` = 纵跨 2 行；`[[merge:2,2]]` = 2×2。
- 标记本身不渲染文字；横并时同一行后面要补占位格（`| |`）保证列数对齐。
- **纵并的续行要写占位格**（可以空着）：`| | D | E |` 里的第一个空单元格
  代表「被上面合并掉的那一列」。

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

**逐表宽度 / 列宽**：`[table]` 的宽度配置是全局的；个别表要不一样时，
在该表任意单元格里写标记（标记不渲染文字，同名取第一个）：

```markdown
| [[table-width:80%]] 项目 | 金额 |
| --- | --- |
| A | 10 |

| [[col-widths:1,3]] 项目 | 金额 |
| --- | --- |
| B | 20 |
```

- `[[table-width:80%]]` / `[[table-width:12cm]]`：该表**总宽**（默认 = 正文宽度）；
- `[[col-widths:3,2,5]]` / `[[col-widths:3cm,auto]]`：该表**列宽**，语义同
  `[table] col_widths`（比例 / 绝对宽度 / `auto` 混写）；
- 写了宽度标记的表按**固定宽度**渲染：`[table] autofit = true` 对这些表不生效；
- 标记作用于整张表，普通 GFM 表与合并单元格表都支持。

**边界**：GFM 单元格只有行内内容（块级列表/公式块/图片不能进单元格）；
行高、厘米列宽、逐单元格边框、合并语法均已支持。

## 8. 图片：`[image]`

| 字段 | 默认 | 说明 |
|---|---|---|
| `width` | 图片原始尺寸 | `"4cm"` / `"120px"` / `"2in"` |
| `align` | 无（左对齐） | `left` / `center` / `right` |
| `space_before` / `space_after` | 无 | 图片段落的段前/段后 |
| `wrap` | 无（inline 独占一行） | `square` 四周型 / `top-bottom` 上下型 / `behind` 衬于文字下方 / `front` 浮于文字上方 |
| `dist` | `0.32cm` | 浮动图片四周留白（带单位） |
| `vpos` | `0` | 浮动图片相对所在段落的垂直偏移（可负，带单位） |

单张图片可覆盖默认：`[[img:pics/a.png width=3cm align=center]]`。

图片后**紧跟图题**时：图片段落自动 `keepNext`（不会图题跑到下一页）、
图题段落 `keepLines`（图题不被拆开）。图题默认居中。

### 浮动图片 / 文字环绕

```markdown
[[img:pics/a.png width=4cm wrap=square align=right dist=0.3cm vpos=0.5cm]]

正文会绕在图片左侧，直到图片下沿。
```

- `wrap=square` 四周型（文字绕排）、`top-bottom` 上下型（图片独占一段高度）、
  `behind` 衬于文字下方、`front` 浮于文字上方（后两种不绕排）；
- `align` 是浮动图片的水平位置（相对页边距 `left` / `center` / `right`）；
  `dist` 是四周留白，`vpos` 是相对所在段落的垂直偏移（都带单位）；
- 锚点是图片所在的段落（通常只有图片），后续段落自动绕排；
- `[image] wrap / dist / vpos` 可设全局默认，单张图片的标记属性优先；
- 非法值报 `E5001`；**紧密型 / 穿越型**的多边形环绕未实现，四边环绕用 `square`。

### 子图：`\\begin{subfigures}`

```markdown
\\begin{subfigures}
\\begin{subfigure #fig:a}
![左图](pics/a.png)

左图说明
\\end{subfigure}
\\begin{subfigure #fig:b}
![右图](pics/b.png)

右图说明
\\end{subfigure}
\\end{subfigures}

\\begin{caption #fig:1}
总图题
\\end{caption}
```

- 子图并排成**无边框表格**：上行图片居中，下行子题注 `（a）说明`、`（b）说明`；
- 子题注可以写在图片下一行（同一段），也可以空一行单独成段；
- 子编号 a/b/c… 按容器内顺序自动生成；**总图题仍由后面的 figure 题注负责**，
  编号/插图清单/REF 都复用现有机制；
- 引用：`图 [[ref:fig:a]]` → `图 1（a）`，按章模式 `图 2-1（a）`。
  子图引用是**构建期静态文本**（不写 REF 域）：因为书签包的是整段子题注，
  REF 域更新后会返回整段说明而不是编号；
- 宽度：默认 n 张平分正文宽的 90%；`[[img:... width=3cm]]` 或
  `[subfigure] width = "45%"` 可覆盖。

### 图注 / 表注：`\begin{note}`

```markdown
\begin{caption #fig:1}
系统架构

\begin{note}
注：数据来源本课题组实验。
\end{note}
\end{caption}
```

| 写法 | 效果 |
|---|---|
| 紧跟图题（或写在题注块内） | **整图注**：图下注释 / 来源注 |
| 写在 `\begin{subfigure}` 内 | **图元注**：渲染到该子图单元格的第三行，与子图一一对齐 |
| 写在表格后面 | **表注**：接在表格下方，仍吃 `[table] space_after` |

- 图注段落挂 `Caption Note` 样式（跟题注同字号、**左对齐**、无首行缩进），
  字号/颜色/段距由 `[styles.caption_note]` 覆盖（见 [config.md](config.md)）；
- 图题后紧跟图注时题注自动 `keepNext`、图注 `keepLines`，不会被分页拆开；
- 图注不进插图清单：清单只取题注第一段。

## 9. 题注 / 交叉引用 / 目录 / 公式 / 脚注

| 语法 | 默认效果 | 相关字段 |
|---|---|---|
| `\begin{caption #fig:1}` | 题注段落（`Caption` 样式：跟正文同字体、**居中**）+ `SEQ 图` 域自动编号 | `[styles.caption] font.*` / `alignment` / `space_*` |
| `\begin{table #tab:1}` | 同上，前缀「表」 | 同上 |
| `\begin{equation #eq:1 number=1}` | 无框三列表格：左空 / 公式居中 / 右编号；默认只给手动编号，`[math] numbering` 可自动编号 | `number` / `[math] numbering` |
| `[[ref:fig:1]]` | `REF` 域，显示目标编号 | 无 |
| `[[toc]]` | `TOC` 域（Word 打开时填充）；级别由 `[toc] levels` 控制 | `[toc] levels` |
| `[[fn:文字]]` | 脚注，编号由 Word 自动生成；`FootnoteText` 单倍行距 | `[styles.footnote] line_spacing`（倍数） |

- **目录级别**：`[toc] levels = 3`（或 `"2-4"`）控制 TOC 域只收录到第几级标题，
  默认 `1-9`；条目仍需 Word 更新域（`updateFields` 已开）。
- **目录条目样式**：Word 内置 `TOC 1..9` 由 Word 管理（实测更新目录时会重置为内置值），
  DocGen 不预置字体/段距；需要改样式请在 Word 里更新目录后手动调 `TOC 1..9`。
- 域缓存值**已烘焙**：`SEQ` / `REF` 写的是真实编号，WPS/预览也能看到正确编号；
  `PAGE` / `TOC` 仍需查看器更新（分页相关）。
- 题注编号按类型独立计数（图 1、图 2、表 1…）。
- **按章编号**：`[document] caption_numbering = "chapter"` 时，图/表编号变成
  「章号-序号」（图 2-1、表 2-1），以一级标题（Heading 1）分章；第一个一级标题之前
  的题注不加章号前缀（保持图 1、图 2）。与 `heading_numbering` 预设无关，
  章号按一级标题顺序计算。
- 按章模式下题注编号是**静态文本**（不再用 `SEQ` 域）：`SEQ` 只会给章内整数，
  更新域会把「2-1」改回「1」；书签仍包住编号，`[[ref:...]]` 的 `REF` 域取到的
  也是「2-1」。

### 文献引用（顺序编码制）

```markdown
正如文献所述[[cite:zhang2024]]，另见[[cite:wang2023,zhao2022]]。

[[bibliography]]
```

- `[[cite:key1,key2]]` → `[1]` / `[1,2]` / `[1-3]`（连续 3 个以上压成区间）；
  编号按**首次出现顺序**分配、构建期烘焙，不依赖 Word 的引文功能。
- **中文条目名**可用，但 TOML 的非 ASCII key 必须加引号：
  `["张三2024"]` + 正文 `[[cite:张三2024]]`；作者/标题等字段直接写中文即可。
- 文献库是独立 TOML 文件（`--refs` 或 `[bibliography] file`）：

  ```toml
  [zhang2024]
  type = "article"              # article/book/conference/thesis/standard/online
  author = ["张三", "李四"]      # 或字符串
  title = "中文排版中的行首禁则研究"
  journal = "排版学报"
  year = "2024"
  volume = "12"
  issue = "3"
  pages = "45-52"
  ```

- `[[bibliography]]` 指定参考文献表位置；**不写则自动追加到文末**。
  标题默认「参考文献」（可用 `[bibliography] title` 改），借 `Heading 1` 样式但取消编号。

参考文献表相关的 `[bibliography]` 设置：

| 字段 | 默认 | 说明 |
|---|---|---|
| `entry_number` | `true` | 条目带 `[n]` 前缀（顺序编码制）；`false` 关闭 |
| `hanging_chars` | `0` | 条目**悬挂缩进**（字符数），如 `2` = 2 字符 |
| `citation_superscript` | `false` | 正文 `[[cite:...]]` 显示为**上标** |
| `author_truncate` | `0` | `>0` 时作者超过 N 名截断；`3` = GB/T 常用「前 3 名」 |
| `et_al` | 自动 | 截断后缀；不写时中文用「等」、西文用「et al.」 |
| `western_initials` | `false` | `true` = 西文作者转「姓前名后 + 名缩写」；中文姓名不动 |

- **作者截断**只对 `author = ["a", "b", …]` 数组生效（字符串作者无法安全拆分）；
  3 名以内不截断，4 名以上列前 N 名 + 后缀。
- **外文姓名**：`western_initials = true` 时 `John A. Hewitt` / `Hewitt, John A.` /
  `Hewitt J A` 都输出 `HEWITT J A`；与 `author_truncate` 可叠加（先缩写再截断）。
  拼音姓名请写成 `Li, Ming`，`Li Ming` 会被当成「名 Li、姓 Ming」。
- 悬挂缩进的数值按正文字号换算（2 字符 × 正文字号），WPS/旧版 Word 也能正确显示。
- 条目按 GB/T 7714 顺序编码制格式化：`[J]` 期刊、`[M]` 专著、`[C]` 会议、
  `[D]` 学位论文、`[S]` 标准、`[EB/OL]` 电子资源；支持 `doi` 字段。
- 错误：引用不存在的 key → `E5004`；有 `[[cite:]]` 却没给文献库 → `E5001`；
  `[[cite:]]` 为空或 `[[bibliography]]` 重复 → `E4001`。
- 限制：只做 **GB/T 7714 数字制**的常见类型；不做 BibTeX 完整语法、CSL 多风格
  （APA/IEEE）引擎，也不生成 Word 原生 `CITATION` 域。

### 插图清单 / 附表清单

```markdown
[[list:figures]]

[[list:tables]]
```

- 条目由题注自动生成：图/表编号 + 题注文字 + **PAGEREF 页码域**；
  标题默认「插图清单」/「附表清单」，可配：

  ```toml
  [list]
  figures = "插图清单"
  tables = "附表清单"
  heading_level = 1      # 标题用哪一级 Heading（1–9）
  ```

- 页码是 `PAGEREF` 域，依赖查看器更新（Word 打开时 `updateFields` 会算；
  不更新域的预览显示占位 1）——与目录/页码同一类限制。
- 清单位置任意：渲染时按全文题注顺序生成，放在正文前也可以。

## 10. 公式：`[math]`

| 字段 | 默认 | 说明 |
|---|---|---|
| `engine` | `auto` | `auto` / `xsl` / `plain` |
| `on_fail` | `plain` | 转换失败时降级为 LaTeX 文本；`error` 则报 `E5002` |
| `xsl` | 自动查找 | `MML2OMML.XSL` 路径；也可用环境变量 `DOCGEN_MML2OMML` |
| `numbering` | `none` | 公式编号：`none`（只用 `number=` 手写）/ `auto`（1、2、3…）/ `chapter`（按一级标题分章，2-1） |
| `number_display_math` | `false` | 让独立 `$$…$$` 也参与同一编号序列；需同时设 `numbering = auto/chapter` |

行内公式 `$x^2$` 与块级 `$$…$$` 都转 OMML（Word 里可编辑）。
没有 XSL（如 Linux CI）时降级为文本，不中断构建。

- 自动编号只作用于 **`\begin{equation}` 命名块**（普通 `$$…$$` 仍不编号）；
  `number=` 手写值优先，并把自动计数同步到该值（`number=7` 后下一项为 8）。
- 带 `#id` 的公式可用 `[[ref:eq:id]]` 引用；编号在构建期烘焙，更新域后仍正确。
- 独立 `$$…$$` 默认**不编号**（推导中间式通常不需要）；`number_display_math = true`
  时与 `\begin{equation}` 共用同一序列。`$$…$$` 没有标签，不能 `[[ref:...]]`——
  需要引用就写成带 `#id` 的 `\begin{equation}`。
- `chapter` 模式下第一个一级标题之前的公式按连续编号（1、2…），不出现 0-1。

## 11. 分节 / 页码 / 页眉页脚 / 封面：`[[sections]]`

不写 `[[sections]]`：单节，页面/页边距取母版（Letter、2.54/3.17cm），无页眉页脚、无页码。

写了之后，每条配置描述一节（**第一条作用于现有节，其余靠 `[[sectionbreak]]` 新建**）：

| 字段 | 默认 | 说明 |
|---|---|---|
| `page.size` | `A4` | `A4` / `A3` / `A5` / **B5** / `Letter` / `Legal` |
| `page.width` / `page.height` | — | 自定义尺寸（cm），覆盖 size |
| `page.margin.top/bottom/left/right` | 母版 | 单位 cm |
| `page.orientation` | `portrait` | `portrait` / `landscape`（横向；自动交换 size 宽高） |
| `page.gutter` | `0` | 装订线，单位 cm（写到 `w:pgMar/@w:gutter`） |
| `page.columns` | `1` | 栏数：`2`，或 `{ count = 2, space = "0.63cm", separator = true }`；每节独立 |
| `numbering.format` | 无 | `decimal` / `upperRoman` / `lowerRoman` / `upperLetter` / `lowerLetter` |
| `numbering.start` | 无 | 重启页码（1 起） |
| `header.text` / `footer.text` | 无 | 页眉/页脚文字；`PAGE` 变成页码域 |
| `header.alignment` / `footer.alignment` | `center` | `left` / `center` / `right` |
| `header.font.*` / `footer.font.*` | 无 | 字体：`name`（中文）/ `latin`（西文）/ `size`（支持中文字号）/ `color` / `bold` / `italic` |
| `header.line` | 无 | 页眉底部线：`single` / `double`（粗上细下）/ `thickThinSmallGap` / `thinThickSmallGap` / `dotted` / `dashed` / `none` |
| `header.line_size` / `line_color` | `1pt` / `000000` | 线宽（`pt`）/ 线色 |
| `header.distance` / `footer.distance` | 母版 | 页眉/页脚距边界（cm） |
| `header.odd` / `header.even` / `header.first` | 无 | 奇数页 / 偶数页 / 首页专用页眉（可写 `text`、`font.*`、`line` 等；`footer` 同理） |
| `cover` | `false` | `true` = 该节页面垂直居中（不是"生成封面内容"） |

分节后每节可独立设栏数——前置单栏、正文双栏：

```toml
[[sections]]
page.columns = 1          # 封面/摘要单栏

[[sections]]
page.columns = { count = 2, space = "0.63cm", separator = false }  # 正文双栏
```

正文里用 `[[sectionbreak]]` 切到下一节；不写标记时内容全部落在最后一节
（旧行为，前面各节是空页）。详见 [word.md](word.md) 的「分节」一节。

**奇偶页不同 + 粗细双线**（学位论文常见）：

```toml
[[sections]]
header.odd.text = "第一章 论文题目"
header.even.text = "XX大学硕士学位论文"
header.line = "double"           # 粗线在上、细线在下
header.line_size = "1.5pt"
header.font.name = "宋体"
header.font.size = "小五"
header.distance = 1.5            # cm
footer.text = "第 PAGE 页"
footer.font.size = "小五"
footer.distance = 1.0
```

- 配了 `header.even` / `footer.even` 会自动打开文档级 `evenAndOddHeaders`；
- 配了 `header.first` / `footer.first` 会自动设置该节 `titlePg`（首页不同）；
- 页眉页脚**每节独立**（不继承上一节），没配文字时仍会写空段落防止串页眉。

## 12. 输出与日志：`[output]`

| 字段 | 默认 | 说明 |
|---|---|---|
| `level` | `warn` | 终端阈值：`log` / `warn` / `err` / `none` |
| `logfile` | 无 | 日志文件路径（相对路径按当前工作目录） |
| `logfile_level` | `log` | 文件阈值，独立于终端 |

命令行 `-q` / `-v` / `--logfile` 覆盖它们；`level = "none"` 只静默打印，**退出码照常**。

## 12.5 PDF 输出：`[pdf]`

docx 是唯一真源；PDF 是**后处理**（先出 docx，再交给外部引擎转）。默认不转。

```toml
[pdf]
enabled = true          # build 时自动转（默认 false）
engine = "auto"         # auto / word / libreoffice
timeout = 120           # 秒
```

命令行（优先级最高）：

```bash
docgen build in.md -c c.toml -o out.docx --pdf             # 生成 out.pdf
docgen build in.md -c c.toml -o out.docx --pdf --pdf-engine word
docgen build in.md -c c.toml -o out.docx --no-pdf          # 覆盖 enabled=true
```

| 引擎 | 依赖 | 特点 |
|---|---|---|
| `word` | Windows + 已装 Microsoft Word | **保真最高**：分页/字体/域按 Word 计算；`ExportAsFixedFormat` |
| `libreoffice` | `soffice`（PATH 或 `DOCGEN_SOFFICE`） | 跨平台；渲染细节与 Word 有差异（**会忽略右页边距**） |
| `auto` | 自动挑 | 优先 `word`，其次 `libreoffice` |

要点：

- PDF 失败**不会删掉已生成的 docx**；报 `E5005`，退出码 **3**（环境错误）。
- LibreOffice 转换用独立 `UserInstallation` 临时配置目录，不会和正在运行的
  LibreOffice 抢锁。
- 版式验收以 Word 为准：LibreOffice 的 PDF 只适合看内容，不适合当分页依据。
- Windows 上 Word 引擎通过 PowerShell COM 调用，**不需要** pywin32；
  PowerShell 5.1 与 7 都支持。

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
| `E5005` | PDF 转换失败（无可用引擎 / 外部工具报错 / 超时） |

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

**中文宋体 + 西文 Times New Roman，行距固定 20 磅**

```toml
[document]
font.name = "宋体"          # 中文
font.latin = "Times New Roman"  # 西文
line_spacing = "20pt"       # 固定值（不写 pt 则是倍数）
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

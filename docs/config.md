# config（TOML）参考

config 是**唯一真源**：所有字号、颜色、字体都来自这里，解析器不写死任何视觉属性。
支持单继承 `based_on`、`@引用`、`include` 合并与 `for = false` 软删除。

> **输入编码**：config / DFM / 文献库统一「UTF-8（含 BOM）优先，GB18030 兜底」
> （best effort，兼容 GBK/GB2312 旧文件）；其它编码报 `E5001`。产物始终 UTF-8。

## 最小示例

```toml
config_version = "0.1"

[document]
font_family = "sans-serif"
font_size = "16px"
line_height = "1.6"

[styles.heading1]
font_size = "2em"
font_weight = "bold"
color = "#111"

[styles.heading2]
based_on = "heading1"     # 单继承：浅合并，子覆盖父
font_size = "1.5em"

[styles.body]
font_size = "@document.font_size"   # @引用：解析成实际值
color = "#333"

[styles.keyword]
color = "#0000FF"
font_weight = "bold"

[styles.keyword_return]
based_on = "keyword"
color = "#FF0000"

[code_block]
background = "#f5f5f5"
font_family = "monospace"

[code_block.python]
based_on = "code_block"   # 语言变体自动以 code_block 为父
color = "#222"
```

`config_version` 必须存在且等于 `0.1`，否则报 `E5001`。

## 三个命名空间

| 命名空间 | 用途 | 展开后的样式名 |
|---|---|---|
| `[document]` | 全局值（供 `@ref` 引用） | 不参与样式表，只做符号 |
| `[styles.*]` | 内容样式（标题、正文、`[文字]{.样式名}`） | `styles.heading1` 等 |
| `[code_block]` / `[code_block.<lang>]` | 代码块样式 | `code_block`、`code_block.python` |

### 图/表按章编号

```toml
[document]
caption_numbering = "chapter"   # 图 2-1 / 表 2-1（默认 continuous：图 1、图 2）
```

以一级标题（Heading 1）分章；第一个一级标题之前的题注保持连续编号。
按章模式下图/表编号写成静态文本（书签仍供 `[[ref:...]]` 使用），
不再用 `SEQ` 域，避免更新域把「2-1」改回「1」。


`[code_block]` 里的**点号键**（`font.name`）会被识别为「基座属性」而不是语言变体；
语言变体只认 `[code_block.<语言>]` 这种表头写法。

## 键名：点号嵌套写法

**只有一种读取形式**：点号键（解析后是嵌套表）：

| 用途 | 例 |
|---|---|
| 字体 | `font.bold` / `font.color` / `font.name` / `font.latin` / `font.size`（支持 `12pt` 或中文字号 `小四`）/ `font.italic` |
| 段落 | `line_spacing`（数字=倍数；`"20pt"`=固定磅值）/ `first_line_chars` / `alignment` / `space_before` / `space_after` |
| 代码块 | `[code_block] background` / `border` |

### 超链接：`[styles.hyperlink]`

默认是 Word 惯例「蓝色 `0563C1` + 单下划线」；需要论文式纯黑可覆盖：

```toml
[styles.hyperlink]
font.color = "000000"   # auto = 不写颜色，跟随正文
underline = "none"      # 去下划线；false 会被样式层当成“删除继承键”
```

| 键 | 默认 | 说明 |
|---|---|---|
| `font.color` | `0563C1` | 6 位十六进制；`auto` 表示跟随段落（正文黑） |
| `underline` | `true` | `true` / `"single"` 开；`"none"` / `"off"` 关 |

> 这里不要写 `underline = false`：样式层把 `false` 统一当作“删除继承键”，
> 该键会在展开时消失；要关下划线请写字符串 `"none"`。


### 段落间距：`space_before` / `space_after`

`[document]` 给默认值，`[styles.body]` / `[styles.headingN]` / `[styles.caption]`
按样式覆盖。两种单位：

| 写法 | 产出 | 说明 |
|---|---|---|
| `"6pt"` / `"12px"` / `"0.2cm"` / `6`（裸数字按磅） | `w:before` / `w:after` | 绝对长度，1pt = 20 twips |
| `"0.5 line"` / `"1 line"` / `"2行"` | `w:beforeLines` / `w:afterLines` | 行单位，百分之一行（0.5 行 = 50） |

```toml
[document]
space_before = "6pt"
space_after = "6pt"

[styles.heading1]
space_before = "1 line"     # 标题前空一行
space_after = "0.5 line"
```

写错单位会**报错**（`E5001`）而不是静默丢弃——「写了不生效」曾是最难查的一类问题。

**表格**：Word 的表格没有「表格前/后间距」属性，标准做法是写到**相邻段落**上。
所以 `[table]` 的间距是这么映射的：

| 配置 | 实际写到 | 效果 |
|---|---|---|
| `[table] space_before` | 表格**前**一段的段后距 | 表格与上文隔开 |
| `[table] space_after` | 表格**后**一段的段前距 | 表格与下文隔开（解决「表格底线贴正文」） |

**图片**：`[image] space_before` / `space_after` 直接作用于图片所在的段落。


### 表格文字：`[table.text]` / `header_bold`

```toml
[table]
header_bold = false          # 表头不加粗

[table.text]
line_spacing = 1.0           # 行距倍数
space_before = "0pt"
space_after = "0pt"
font.size = "9pt"
font.name = "黑体"
```

表格文字默认继承 `Normal`；`[table.text]` 只写显式配置的键。字段语义与 `[styles.*]` 相同（`font.*` / `line_spacing` / `space_*`），字体支持中文（`font.name`）与西文（`font.latin`）分开设置。

### 表格线：`[table] style` / `line_*` / `edges` / `row_lines`

```toml
[table]
style = "three_line"            # three_line / grid / none / custom
line_style = "single"           # single / double / dashed / dotted / none
line_size = "1pt"               # 统一线宽（三线表下为旧行为：三条线都用它）
outer_line_size = "1.5pt"       # 顶线/底线（粗，默认 1.5pt）
header_line_size = "0.5pt"      # 栏目线（细，默认 0.5pt）
aux_line_size = "0.5pt"         # 辅助线（默认同栏目线）
header_line = true              # false = 二线表（无栏目线）
line_color = "000000"           # 000000 / 999999 / auto
row_lines = false               # true 或线型：每行底部一条横线
edges = { ... }                 # 仅 style = "custom"：逐边线型
header_repeat = true            # 跨页重复表头（默认）
header_keep_with_body = true    # 表头与首行同页，防止「表头孤行」（默认）
rows_keep_together = true        # 所有表格行不跨页（默认；false = 允许行内断行）
cell_margin = "0.1cm"            # 单元格内边距（四边统一；可加 cell_margin_left 等逐边覆盖）
decimal_align = [2]             # 数值列（1 起）：小数点/个位对齐，可多列
```

- **数值对齐**：`decimal_align = [2, 4]` 让这些列的数据行按小数点对齐，
  整数行按个位对齐（只处理纯数字；表头与非数字单元格保持原样）。
  实现细节与 Word 实测见 [word.md](word.md) 的「数值列」。有效位数一致属于内容，工具不检查。

- **三线表粗细**：顶/底粗、栏目线细，三者必须**有区分**（默认 1.5pt / 0.5pt）；
  各期刊磅值不同，用 `outer_line_size` / `header_line_size` 覆盖。
  `line_size` 是统一线宽（旧行为），优先级：具体键 > `line_size` > 默认。
- **二线表**：`header_line = false`，只保留顶线与底线（横向阅读逻辑更适用）。
- **辅助线**：竖线/横线之外，`[[aux]]` 写在某行任一单元格里，给该行**上方**加一条
  辅助线（合计 / 小计 / 统计处理结果行），线宽由 `aux_line_size` 控制。
- `edges` 可用的边：`top` `left` `bottom` `right` `insideH` `insideV`；
  未写的边默认 `none`。写错边名报 `E5001`。
- `line_size` / `line_color` 对预设（`grid` / `three_line`）与 `custom` 都生效。
- **斜线表头**：单元格里写 `[[diag:右上;左下]]`（分隔符 `;`），
  渲染成 `w:tcBorders/tl2br` + 两段文字（右上右对齐、左下左对齐）。
- `header_keep_with_body`：表头行段落写 `w:keepNext`，强制表头与首行数据同页；
  表头行另写 `cantSplit`（行内不分页）。**默认开启，不建议关**——关掉会出现
  「表头单独留在页底」的排版缺陷（实测数据见 [word.md](word.md) 的「表头不能孤行」）。
- `rows_keep_together`：所有行写 `cantSplit`，要求行内不跨页（默认开启）。
  长表格里关闭它 Word 会把一行拆到两页；表头行无论如何都不拆。
- `cell_margin` 写 `w:tblCellMar`：四边统一；`cell_margin_top/bottom/left/right`
  可逐边覆盖。不写则保留 Word 默认（左右 0.19cm、上下 0），单位必须带 `cm`/`pt`。
- **表题同页**：表题写在表格**上方**且 `kind=table` 时，题注段自动 `keepNext`，
  和表格绑在同一页；题注写在表格下方则不绑定（顺序错误应显式改）。
- 表格与正文的间距仍用 `[table] space_before` / `space_after`（写到相邻段落）。

> 完整字段表见 [cheatsheet.md](cheatsheet.md)，默认效果与边界见 [manual.md](manual.md)。

行内样式（`[文字]{.样式名}`）的样式里也能写这四个段落级键
（`alignment` / `first_line_chars` / `space_before` / `space_after`），作用于所在段落。

### 中文排版：避头尾 / 标点压缩

默认全开——正式中文文档里「标点出现在行首」是排版差错：

```toml
[document]
east_asia_lang = "zh-CN"        # 决定 Word 用哪套禁则表（zh-TW / ja-JP / ko-KR）
kinsoku = true                  # 按中文习惯控制首尾字符（避头尾）
overflow_punct = true           # 行尾标点允许溢出边界
compress_punctuation = true     # 标点压缩：优先把标点挤回上一行
auto_space = true               # 中西文、中文与数字之间自动留白
```

为什么需要这些：`python-docx` 自带模板的 `docDefaults` 是 `eastAsia="en-US"`，
此时 Word 即使「避头尾」开着，仍会把 `）」` 放到行首；改成 `zh-CN` 后同一段文本
从 2 处降为 0 处（实测数据见 [word.md](word.md) 的「避头尾」一节）。

值写错会报 `E5001`（`kinsoku = "maybe"`、`east_asia_lang = "chinese"` 都报错）。

### `alignment`：段落对齐

`[document] alignment` 是**默认值**，`[styles.body] alignment` / `[styles.headingN] alignment`
覆盖它。注意它是默认值：只设 `[document]` 时**标题也会跟着对齐**。

| 写法 | 产出 |
|---|---|
| `left` / `start` | `w:jc w:val="left"` |
| `right` / `end` | `w:jc w:val="right"` |
| `center` / `centre` | `w:jc w:val="center"` |
| `justify` / `both` | `w:jc w:val="both"` |
| 其它任何值 | 退回左对齐（不报错——对齐是纯外观，写错不该让整篇构建失败） |

**逐段对齐 / 缩进**：DFM 没有块级样式语法，但 `[文字]{.样式名}` 的样式里若写了
`alignment` 或 `first_line_chars`，会作用到**它所在的段落**。封面署名行这类需求：

```toml
[styles.body]
first_line_chars = 200      # 正文首行缩进 2 字符

[styles.signature]
first_line_chars = 0        # 署名行不缩进
alignment = "center"
```

```markdown
[学号：5120242907　姓名：官畅宇　班级：软件2406]{.signature}
```

只认这两个段落级键；间距等其它段落属性仍由正文段落统一管理。

### 题注：`[styles.caption]`

题注段落用的是 Word 内置 `Caption` 样式，所以 `[styles.caption]` 的**字体类**
属性（`font.name` / `font.size` / `font.color` / `font.bold` …）会写进该样式，
题注文字与编号一起生效。同理 `[styles.body]` 的字体类属性写进 `Normal`。

段落级键同样生效（与正文共用一套读取）：`alignment`、`first_line_chars`。

- **默认居中**：学术排版规范要求图题在图片正下方居中，模板里的 `Caption` 样式
  预置了 `w:jc=center`；想左对齐就写 `[styles.caption] alignment = "left"`。
- **与图片同页**：图片段落自动带 `keepNext`（仅当后面紧跟图题时），图题带
  `keepLines`，所以两者不会被分页拆开（详见 [docs/word.md](word.md)）。

### 有序列表编号

每个有序列表是**独立列表**，各自从 1 开始（Markdown 里两个列表就是两个列表，
Word 里也这样）。嵌套的有序列表同样独立计数。
实现上每个列表分配一个 `w:num` 实例，复用 `List Number` 样式的 `abstractNum`
（外观不变，只换计数器）。

> ⚠️ **扁平键不会被读取**：`font_weight` / `font_style` / `font_size` /
> `font_family` / `text_decoration` 这些是早期 HTML 后端的写法。
> HTML 后端已移除，写它们**不会报错，但也不会生效**——没有后端去读。
> 排查方式：`docgen dump-styles -c config.toml` 看实际展开值。
> （`tests/test_config_source_of_truth.py` 守着「config 声明了就要到产出」。）

## `[output]`：输出与日志

```toml
[output]
level = "warn"          # 终端阈值：log | warn(默认) | err | none
logfile = ""            # 空 = 关闭；相对路径按当前工作目录解析
logfile_level = "log"   # 文件阈值，**独立于终端**（通常更详细）
```

| 级别 | 含义 |
|---|---|
| `log` | 全部输出（`-v/--verbose` 等价于此） |
| `warn` | **默认**：只出警告与错误 |
| `err` | 只出错误诊断；命令**结果照常打印**（`-q/--quiet` 等价于此） |
| `none` | **完全静默**（连结果也不打印），只留退出码 |

> `none` 与 `-q` 不一样：`-q` 只是「别刷日志」，脚本仍能拿到结果；
> `none` 是「什么都别打印」，**但退出码照常返回**（0/1/2），不会被静默掉。
> 静默只针对**终端**：``logfile`` 仍按 ``logfile_level`` 照常记录。

- **分流**：命令的**结果**走 stdout（`build` 的「已生成 …」、`check` 的 `OK:`、
  `check --json` 的 JSON），**诊断**走 stderr。`--json` 时 stdout 只有 JSON。
- **logfile**：默认关闭、**覆盖写**、单文件、无滚动。头部含
  docgen / python / 平台 / config / input，尾部含退出码；
  环境变量里的 `*_TOKEN`、`*_PASSWORD` 等敏感键会被过滤。
- CLI 的 `-q` / `-v` / `--logfile` **只影响终端**，不改文件内的级别。

## `[pdf]`：生成后自动转 PDF

docx 是唯一真源；PDF 是后处理（先出 docx，再交外部引擎转）。默认关闭。

```toml
[pdf]
enabled = false         # true = build 时自动转（也可用 --pdf）
engine = "auto"         # auto / word / libreoffice
timeout = 120           # 秒
```

| 引擎 | 依赖 | 说明 |
|---|---|---|
| `word` | Windows + Microsoft Word | 保真最高（分页/字体/域按 Word 算）；不需要 pywin32 |
| `libreoffice` | `soffice`（PATH 或 `DOCGEN_SOFFICE`） | 跨平台；会忽略右页边距，不适合当分页依据 |
| `auto`（默认） | — | 优先 Word，其次 LibreOffice；都没有报 `E5005` |

- PDF 输出路径 = docx 同目录同名（`out.docx` → `out.pdf`）。
- 优先级：`--no-pdf` > `--pdf` > `[pdf] enabled`；`--pdf-engine` 覆盖 `engine`。
- 转换失败**不会删已生成的 docx**，报 `E5005`、退出码 3；非法配置报 `E5001`。
- 版式验收以 Word 为准，LibreOffice 的 PDF 只适合看内容。

## `[bibliography]`：文献库与参考文献表

配合 `[[cite:key]]` / `[[bibliography]]` 使用（顺序编码制，GB/T 7714 子集）。

```toml
[bibliography]
file = "references.toml"   # 文献库；相对输入文件所在目录（也可用 --refs 覆盖）
title = "参考文献"          # 文献表标题（借 Heading 1 样式但取消编号）
entry_number = true        # 条目带 [n] 前缀（默认 true）
hanging_chars = 2          # 悬挂缩进（字符数，默认 0）
citation_superscript = false  # 正文引用上标（默认 false）
author_truncate = 3        # 作者超过 N 名截断（默认 0 = 不截断）
et_al = ""                 # 截断后缀；空 = 中文「等」/ 西文「et al.」
```

文献库是独立 TOML，每个条目一个 `[key]` 表：

```toml
[zhang2024]
type = "article"           # article/book/conference/thesis/standard/online
author = ["张三", "李四"]   # 或字符串
title = "中文排版中的行首禁则研究"
journal = "排版学报"
year = "2024"
volume = "12"
issue = "3"
pages = "45-52"
```

- 编号按**首次引用顺序**分配，构建期烘焙；`[[cite:a,b]]` → `[1,2]`。
- **中文条目名**：TOML 非 ASCII key 必须加引号（`["张三2024"]`），正文写
  `[[cite:张三2024]]`；作者/标题字段直接写中文即可。
- 不写 `[[bibliography]]` 时参考文献表自动追加到文末。
- 引用不存在的 key 报 `E5004`；有 `[[cite:]]` 但没配文献库报 `E5001`。
- 不支持 BibTeX 完整语法与 CSL 多风格（APA/IEEE）引擎；不做 Word 原生引文域。

## `[toc]`：目录级别

```toml
[toc]
levels = 3      # 只收录 1–3 级标题（默认 1-9；也可写 "2-4"）
```

条目样式（Word 内置 `TOC 1..9`）由 Word 管理：Word 更新目录时会重置这些样式，
DocGen 不预置字体/段距；需要改样式请在 Word 更新目录后手动调整。

## `[subfigure]`：子图

```toml
[subfigure]
width = "45%"      # 子图图片宽度；空 = n 张平分正文宽的 90%
```

配合 `\\begin{subfigures}` / `\\begin{subfigure #fig:a}` 使用。单个子图的
`[[img:... width=...]]` 优先于这里的默认值。

## `[math]`：公式

```toml
[math]
engine = "auto"       # auto / xsl / plain
on_fail = "plain"     # plain = 降级文本；error = 报 E5002
xsl = ""              # MML2OMML.XSL 路径；也可用 DOCGEN_MML2OMML
numbering = "none"    # none / auto / chapter（公式自动编号）
number_display_math = false  # true = 独立 $$…$$ 也编号（需 numbering=auto/chapter）
```

`numbering = "auto"` 给 `\begin{equation}` 按出现顺序编号（1、2、3…）；
`"chapter"` 按一级标题分章（2-1）。手动 `number=` 优先，并同步自动计数。
带 `#id` 的公式可用 `[[ref:eq:id]]` 引用。

## `[list]`：插图清单 / 附表清单

配合 `[[list:figures]]` / `[[list:tables]]` 使用：

```toml
[list]
figures = "插图清单"
tables = "附表清单"
heading_level = 1      # 1–9；用 Heading N 样式但取消编号
```

条目由题注自动生成（编号 + 题注文字 + `PAGEREF` 页码域）；页码依赖查看器更新。

## `[inline]`：语义名 -> 样式名映射

Markdown/DFM 语法产出的是**语义名**（`**粗体**` → `strong` 等），默认**同名**，
所以不写 `[inline]` 时行为完全不变；写了就能重定向到任意样式：

```toml
[inline]
sup = "sup_caret"          # ^x^ 改用 [styles.sup_caret]

[styles.sup_caret]
font.size = "7pt"
font.color = "C00000"
```

| 语义名 | 触发语法 |
|---|---|
| `strong` | `**粗体**` |
| `em` | `*斜体*` |
| `strike` | `~~删除~~` |
| `sup` | `^上标^` / `[文字]{.sup}` |
| `sub` | `~下标~` / `[文字]{.sub}` |

> 重定向后**必须**声明目标样式，否则报 `E1003`，且错误信息会**暴露映射链**：
>
> ```
> E1003:^上标^ 或 [文字]{.sup} 映射到 sup_caret（来自 [inline].sup），
>       但 config 缺少 [styles.sup_caret]
> ```

内置样式名（**无需声明即可引用，但只有声明了才会有格式**）：
`strong`、`em`、`strike`、`sup`、`sub`
—— 分别对应 `**粗体**`、`*斜体*`、`~~删除~~`、`E=mc^2^`、`H~2~O`。

> ⚠️ **最常见的坑**：`**粗体**` 用的是**内置样式名 `strong`**，不是自定义名。
> config 若不声明 `[styles.strong]`，产物里**不会加粗**（内容照常输出，只是没有格式）——
> 因为「config 是唯一真源」，引擎不写死任何视觉属性。
>
> ```toml
> [styles.strong]        # ← 必须写这一段，**粗体** 才会真的粗
> font.bold = true
> ```
>
> 对照表见 [examples/features/README.md](../examples/features/README.md)。

## `include`：多文件合并

```toml
# config.toml
config_version = "0.1"
include = ["base.toml", "overrides.toml"]

[document]
font_size = "16px"
```

合并规则：

1. 按 `include` 顺序依次合并，**后者覆盖前者**；
2. 自身文件最后合并，**覆盖所有 include**；
3. 每个文件自己也可以有 `include`（递归），出现循环报 `E5001`；
4. 合并是**逐表浅合并**：`[styles.body]` 只覆盖同名的键，其它键保留。

## `based_on`：单继承

- 浅合并：父属性先铺开，子属性覆盖同名键，未提到的键保留。
- 深度上限 **8 层**，超过报 `E1002`；出现环（含自引用）报 `E1001`。
- `based_on` 指向不存在的样式报 `E5001`。
- `[code_block.<lang>]` 不写 `based_on` 时默认继承 `code_block`。

## `@ref`：引用实际值

```toml
[document]
font_size = "16px"

[styles.body]
font_size = "@document.font_size"   # -> "16px"

[styles.base]
color = "#abc"

[styles.use]
color = "@styles.base.color"        # -> "#abc"
```

- 可指向 `[document]`、`[styles.*]`、`[code_block*]` 命名空间；
- 支持链式引用（`a` 引用 `b`，`b` 引用 `document`），解析到最终值；
- 指向不存在的键报 `E1003`；循环引用报 `E1001`。

## `for = false`：软删除

```toml
[styles.base]
color = "red"
font_weight = "bold"

[styles.child]
based_on = "base"
color = false        # 删除从父继承来的 color，结果只剩 font_weight
```

## CLI

```bash
# 展开后的最终值（继承 + @ref 都已解析）
docgen dump-styles -c config.toml

# 合并后的原始表（保留 based_on 与 @ref，便于排查）
docgen dump-styles -c config.toml --raw

# 校验内容里的样式引用与图片路径
docgen check input.md -c config.toml          # 文本错误 + 退出码
docgen check input.md -c config.toml --json   # {"ok": false, "errors": [...]}
```

`check --json` 输出：

```json
{
  "ok": false,
  "errors": [
    {"file": "input.md", "line": 3, "col": 0, "code": "E1003", "message": "引用了不存在的样式: nope"}
  ]
}
```

退出码：`0` 通过；`1` 内容错误（样式引用/图片缺失）；`2` 配置错误（文件缺失、版本不符、
继承环、深度超限、`@ref` 不存在）。

## 不支持

多继承、深合并、跨命名空间继承、`include` 指向 URL、config 变量插值（除 `@ref` 外）。

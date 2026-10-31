# DocGen 速查表

> 一页速查：**写什么 → 用哪个字段**。细节（默认值来源、OOXML 原理、限制）见
> [manual.md](manual.md)；完整语法见 [config.md](config.md) / [dfm.md](dfm.md)。

## 1. 最常用 config（直接抄）

```toml
config_version = "0.1"

# ── 文档默认 ─────────────────────────────
[document]
font.name = "宋体"
font.size = "12pt"
line_spacing = 1.5            # 1.15（母版默认）/ 1.5 / 2
heading_numbering = true      # 标题多级编号（默认开）

# ── 标题 ────────────────────────────────
[styles.heading1]
font.name = "黑体"
font.size = "18pt"
font.bold = true
font.color = "000000"

# ── 正文 ────────────────────────────────
[styles.body]
first_line_chars = 200        # 首行缩进 2 字符
alignment = "justify"         # left / right / center / justify
space_before = "0"
space_after = "6pt"

# ── 行内语义（不声明就不生效！）──────────
[styles.strong]
font.bold = true
[styles.em]
font.italic = true

# ── 代码块 ──────────────────────────────
[code_block]
background = "F5F5F5"
border = "CCCCCC"

# ── 表格 ────────────────────────────────
[table]
style = "three_line"          # three_line / grid / none / custom
header_repeat = true
col_widths = [3, 2, 5]        # 相对比例

# ── 图片 ────────────────────────────────
[image]
width = "6cm"
align = "center"

# ── 输出与日志 ───────────────────────────
[output]
level = "warn"                # log / warn / err / none
logfile = ""
```

## 2. 字段总表

### `[document]`
| 字段 | 默认 | 例 |
|---|---|---|
| `font.name` / `font.size` | 主题字体 / 11pt | `"宋体"` / `"12pt"` |
| `line_spacing` | 1.15 | `1.5` |
| `heading_numbering` | `true` | `false` |
| `heading_indent` | 母版（`left 720 hanging 360`） | `false` / `0` / 表 |
| `alignment` | 继承 | `"center"` |
| `space_before` / `space_after` | 无 | `"6pt"` / `"0.5 line"` |
| `hr.style` / `hr.color` / `hr.size` | `single` / `auto` / `6` | — |

### `[styles.*]`（`body`、`heading1..9`、`caption`、`strong`、`em`、`strike`、`sup`、`sub`、任意名）
| 字段 | 作用 |
|---|---|
| `font.name` / `size` / `color` / `bold` / `italic` / `underline` / `strike` | 字体类 |
| `line_spacing` | 行距（倍数） |
| `first_line_chars` | 首行缩进（**字符**单位，200 = 2 字符） |
| `alignment` | `left` / `right` / `center` / `justify` |
| `space_before` / `space_after` | 段前/段后 |
| `based_on` | 继承另一段样式 |

### `[inline]`
| 写法 | 例 |
|---|---|
| 语义名 → 样式名 | `sup = "sup_caret"` |

### `[code_block]` / `[code_block.<语言>]`
| 字段 | 默认 | 例 |
|---|---|---|
| `font.name` / `size` / `color` | Consolas / 继承 | `font.name = "Consolas"` |
| `background` | 无 | `"F5F5F5"` |
| `border` | 无 | `"CCCCCC"` |
| `inline_background` | `F2F2F2` | 空串 = 不画 |

### `[table]`
| 字段 | 默认 | 例 |
|---|---|---|
| `style` | `three_line` | `grid` / `none` / `custom` |
| `header_repeat` | `true` | `false` |
| `col_widths` | 均分 | `[3, 2, 5]` |
| `line_style` | `single` | `double` / `dashed` / `dotted` |
| `line_size` | 母版（表头线 1pt） | `"1pt"` / `"0.5pt"` / `"8px"` |
| `line_color` | `auto` | `"000000"` |
| `edges` | 无（仅 `custom` 用） | `{ top = "single", insideH = "dashed" }` |
| `row_lines` | `false` | `true` / `"dashed"`（每行底部横线） |
| `space_before` / `space_after` | 无 | 表格与上下文间距 |

`edges` 可用的边：`top` `left` `bottom` `right` `insideH` `insideV`。

### `[image]`
| 字段 | 默认 | 例 |
|---|---|---|
| `width` | 原始尺寸 | `"6cm"` |
| `align` | 无（左） | `"center"` |
| `space_before` / `space_after` | 无 | `"6pt"` |

### `[[sections]]`（数组，每项一节）
| 字段 | 默认 | 例 |
|---|---|---|
| `page.size` | `A4` | `A4` / `A3` / `Letter` / `Legal` |
| `page.margin.top/bottom/left/right` | 母版 | `2.5`（cm） |
| `numbering.format` | 无 | `decimal` / `upperRoman` |
| `numbering.start` | 无 | `1` |
| `header.text` / `footer.text` | 无 | `"第 PAGE 页"` |
| `cover` | `false` | `true`（该节垂直居中） |

### `[output]`
| 字段 | 默认 | 说明 |
|---|---|---|
| `level` | `warn` | `log` / `warn` / `err` / `none` |
| `logfile` | 无 | 日志文件 |
| `logfile_level` | `log` | 文件阈值 |

### `[math]`
| 字段 | 默认 | 说明 |
|---|---|---|
| `engine` | `auto` | `auto` / `xsl` / `plain` |
| `on_fail` | `plain` | `error` 则报 `E5002` |
| `xsl` | 自动查找 | MML2OMML.XSL 路径 |

## 3. 语法标记

| 标记 | 作用 |
|---|---|
| `[[img:path width=3cm align=center]]` | 图片（独占一行时是块级图） |
| `[[pagebreak]]` | 分页 |
| `[[sectionbreak]]` | 切到下一个 `[[sections]]` 配置的新节 |
| `[[toc]]` | 目录（TOC 域） |
| `[[ref:fig:1]]` | 交叉引用（REF 域） |
| `[[fn:文字]]` | 脚注 |
| `[[diag:年份;项目]]` | **表格单元格**里的斜线表头（用 `;` 分隔，不能用 `\|`） |
| `` `code` `` | 行内代码（Consolas + 灰底） |
| `$x^2$` / `$$…$$` | 行内 / 块级公式 |
| `**粗**` `*斜*` `~~删~~` `^上^` `~下~` | 行内语义（需在 config 声明样式） |
| `[文字]{.样式名}` | 套任意样式；样式里的 `alignment`/`first_line_chars`/`space_*` 作用于该段 |
| `\begin{caption #fig:1}` … `\end{caption}` | 图题（SEQ 自动编号） |
| `\begin{table #tab:1}` … | 表题 |
| `\begin{equation #eq:1 number=1}` … | 编号公式（三列表格，编号带书签） |

## 4. 单位

| 场景 | 写法 |
|---|---|
| 长度/字号/图片宽 | `12pt` `16px` `2cm` `10mm` `1in` |
| 行距 | 倍数：`1.5` |
| 段前/段后 | `6pt` / `12px` / `0.5 line` / `1行` / 裸数字（磅） |
| 首行缩进 | **字符**：`200` = 2 字符 |
| 表格线宽 | `1pt` / `0.5pt` / `8px`（转 1/8 磅） |
| 表格列宽 | 相对比例：`[3, 2, 5]` |
| 表格间距 | 同段前/段后 |

## 5. CLI

```bash
docgen check  input.md -c config.toml [--strict] [--json]   # 校验
docgen build  input.md -c config.toml -o out.docx           # 生成 .docx
docgen dump-ir input.md                                     # 看解析出的 IR（排查语法）
docgen dump-styles -c config.toml                           # 看展开后的样式（排查样式）
docgen bug-report --output r.txt                            # 打包环境信息
```

全局开关放在子命令**前**：`-q` / `-v` / `--logfile FILE`。
退出码：`0` 成功 / `1` 内容错误 / `2` 用法或 config 错误 / `130` 中断。

## 6. 错误码

| 码 | 含义 | 码 | 含义 |
|---|---|---|---|
| `E1001` | 循环继承 | `E3002` | `\begin` 名字不一致 |
| `E1002` | 继承过深 | `E4001` | 语法错误 |
| `E1003` | 样式不存在 | `E5001` | config/母版错误 |
| `E2001` | 未知语言 | `E5002` | 公式转换失败 |
| `E2010` | keywords 非法 | `E5003` | 分节配置错误 |
| `E3001` | 标记未闭合 | `E5004` | 引用目标不存在 |

## 7. 不写 config 时的默认效果

| 元素 | 默认 |
|---|---|
| 页面 | Letter 21.59×27.94cm；边距 上下 2.54 / 左右 3.17cm |
| 正文 | 主题字体 11pt、段后 10pt、1.15 倍行距、无首行缩进、左对齐 |
| 标题 1 / 2 / 3+ | 14pt 粗 `365F91` / 13pt 粗 `4F81BD` / 11pt 粗 `4F81BD`；自动编号 |
| 行内 `**粗**` 等 | **无格式**（config 不声明就不加粗/倾斜/删除线） |
| 表格 | 三线表（顶/底 + 表头下 1pt 横线）、表头加粗、跨页重复表头、列宽均分 |
| 图片 | 原始尺寸、左对齐、无段距 |
| 题注 | `Caption` 样式：跟正文同字体、**居中**、`SEQ` 自动编号 |
| 代码块 | Consolas、1.0 行距、无底纹/边框 |
| 行内代码 | Consolas + 底纹 `F2F2F2` |
| 分节 | 单节、无页眉页脚、无页码 |
| 公式 | OMML（缺 XSL 时降级为 LaTeX 文本） |
| 输出 | 终端 `warn`、不写日志文件 |

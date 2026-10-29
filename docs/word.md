# Word（docx）后端

**唯一的渲染后端**。DFM + config → IR → OOXML（`.docx`），Word 里可继续编辑。

> 早期另有一个 HTML 后端，用作 IR 设计的参照实现（「HTML 对了 Word 不对 →
> 问题在渲染层」）。它已移除：维护成本高于收益、需求很少。现在只有这一条渲染路径。

## 用法

```bash
# 默认产出 .docx
docgen build input.md -c config.toml -o output.docx

# 显式指定格式（目前只接受 docx）
docgen build input.md -c config.toml -o output.docx --format docx
```

退出码与剪枝版一致：`0` 成功、`1` 内容错误、`2` 配置/文件错误。

## config 口径（手册 §6.1）

完整版用**点号键**，与剪枝版的下划线扁平键不同：

```toml
config_version = "0.1"

[document]
font.name = "宋体"
font.size = "12pt"
line_spacing = 1.5

[styles.heading1]
font.name = "黑体"
font.size = "18pt"
font.bold = true
font.color = "1F3864"

[styles.body]
first_line_chars = 200     # 首行缩进 2 字符
```

展开后 `font.name` 变成嵌套结构（`{"font": {"name": "宋体"}}`），渲染层按此读取。
`color` 写 `RRGGBB` 或 `#RRGGBB` 都接受（OOXML 里不带 `#`）。

### 样式值写到哪：run / 样式定义 / 载体样式

| config | 写到 | 为什么 |
|---|---|---|
| `[styles.body]` 字体类 | `Normal` 样式 | 正文段落默认继承它，不必每个 run 重复 |
| `[styles.caption]` 字体类 | `Caption` 样式 | 题注段落挂的是内置 `Caption` |
| `[styles.headingN]` 字体类 | **run** 与 `Heading N` 样式定义 | run 决定当前文字；样式定义决定 Word 样式面板与「新敲一个标题」 |
| `[styles.<任意>]` 字体类 | run | `[文字]{.样式}` 这类行内用法 |

两个容易踩的 Word 细节：

- **中文取 `w:eastAsia`**：`font.name` 会同时写 ascii/hAnsi/eastAsia/cs。
  代码块与行内代码是例外——等宽字体没有中文字形，`eastAsia` 留给样式链。
- **主题属性优先于显式值**：母版的 Heading 带 `w:asciiTheme` / `w:color w:themeColor`，
  不清掉的话「config 设了颜色/字体」实际不生效。写 config 时会一并清除。

## 模块划分

| 模块 | 职责 |
|---|---|
| [render/docx.py](../src/docgen/render/docx.py) | IR → docx：块级节点 → Word 段落/表格，行内样式 → run 属性 |
| [render/ooxml.py](../src/docgen/render/ooxml.py) | **所有** `OxmlElement` 构造集中于此（命名空间、属性拼写、陷阱） |
| [render/template.py](../src/docgen/render/template.py) | 母版加载与版本；把 `[document]` 的排版值写进样式 |
| [units.py](../src/docgen/units.py) | 单位换算：`12pt` / `16px` / `1.5em` / 纯数字 → 磅 |

## 已处理的 OOXML 陷阱（手册 §17.1）

| 陷阱 | 处理 |
|---|---|
| 中英混排字体回退 | `apply_font` 一次写全四个 `w:rFonts`（ascii/hAnsi/eastAsia/cs） |
| 首行缩进单位 | 用 `w:firstLineChars`（字符单位），不用 `w:firstLine` |
| 段前段后单位 | 用 `w:beforeLines` / `w:afterLines` |
| 标题不进导航窗格 | 每个 `HeadingN` 样式写 `w:outlineLvl` |
| 域不自动更新 | `settings.xml` 写 `<w:updateFields w:val="true"/>` |
| 样式 id 查找 | 用样式**名**（`styles["Heading1"]`）而不是 style_id |

## 母版（手册 §14.1）

母版**由代码确定性生成**：[`render/template_build.py`](../src/docgen/render/template_build.py)
在 python-docx 默认模板上补齐 §14.1 里默认模板缺失的槽位，`build_template()` 每次构建都会补齐（幂等）：

| 槽位 | 处理 |
|---|---|
| `Heading 1`~`Heading 9` | 确保带 `w:outlineLvl`（导航窗格与目录依赖） |
| 多级标题编号 | `numbering.xml` 追加 `numId=100`：`Heading1`→`1`、`Heading2`→`1.1`…… |
| `TOC 1`~`TOC 9` | 默认模板没有 → 创建（目录域按级别套用） |
| `settings.xml` | `<w:updateFields w:val="true"/>` |
| 字体 | 引擎写 `[document]` 时统一处理四个 `rFonts` 属性 |

细节见 [src/docgen/templates/default/README.md](../src/docgen/templates/default/README.md)，
校准断言见 [tests/test_template.py](../tests/test_template.py)。

## 数学（W2）

链路：**LaTeX → MathML（`latex2mathml`）→ OMML（Office 的 `MML2OMML.XSL`）**，
插进段落的是 `m:oMath`，所以公式在 Word 里**可编辑**（不是图片、不是文本）。

```toml
[math]
engine = "auto"        # auto | xsl | plain
on_fail = "plain"      # plain（降级成 LaTeX 文本）| error（报 E5002）
xsl = 'C:\...\MML2OMML.XSL'   # 可选；也可用环境变量 DOCGEN_MML2OMML
```

- **XSL 从哪来**：Windows 版 Office 随装（`C:\Program Files\Microsoft Office\root\Office16\MML2OMML.XSL`）；
  本机已检测到。Linux CI 通常没有 → `auto` 自动降级 `plain`，构建不会因为公式失败。
  需要公式的场景可在 CI 里装 LibreOffice 并设置 `DOCGEN_MML2OMML`。
- **失败可观测**：`on_fail="error"` 时报 `E5002`；`plain` 时降级并记录原因
  （`latex2mathml` 对非法输入的异常 `str()` 为空，代码里用类型名兜底）。
- **通率**：[tests/test_math.py](../tests/test_math.py) 的 40 条公式测试集当前 **40/40 = 100%**
  （手册验收要求 > 90%）。

## 编号 / 题注 / 交叉引用（W3）

| 能力 | 实现 |
|---|---|
| 标题多级编号 | 母版 `numId=100`；映射显式化在 [`numbering.heading_numbering()`](../src/docgen/numbering.py)：`level → (ilvl, HeadingN)` |
| 题注 | `\begin{caption #fig:1}` / `\begin{table #tab:1}` / `\begin{equation #eq:1}` → 书签 + `SEQ 图 \* ARABIC` 域 + **Caption** 样式 |
| 交叉引用 | `[[ref:fig:1]]` → `REF fig:1 \h` 域（域结果即题注编号，`\h` 带超链接） |
| 目录占位 | `[[toc]]` → `TOC \o "1-9" \h \z \u` 域；`settings.xml` 已带 `updateFields`，打开自动填充 |
| 题注编号 | 按类型独立计数（图 1、图 2、表 1…），由 `SEQ` 域在 Word 里递增 |
| 校验 | 引用目标不存在 → `E5004`；标签重复 → `E4001`（`check --strict` 一并报告） |

```markdown
\begin{caption #fig:1}
系统架构
\end{caption}

见图 [[ref:fig:1]]。     <!-- Word 里显示「图 1」，随编号自动更新 -->

\begin{equation #eq:main number=1}
$$
E = mc^2
$$
\end{equation}
```

**公式编号**渲染成**无边框三列表格**（左空 / 中公式 / 右编号），编号带书签，
所以 `[[ref:eq:main]]` 也能引用它。用表格而不是制表位，是因为制表位在不同 Word 版本里表现不一致。



**W0 已实现**：标题（`Heading 1`…`Heading 6` + `outlineLvl`）、段落（行距 + 首行缩进）、
行内样式（`Styled` → run 字体/加粗/斜体/删除线/颜色，值全部来自 config）、
代码块（等宽字体，支持 `[code_block.<lang>]` 变体）、有序/无序列表、
引用（`Quote`）、分隔线、分页（`w:br type="page"`）、表格（表头加粗 + 边框）、图片（写入 `word/media/`）。

**W1 已实现**：上下标（`H~2~O`、`E=mc^2^`、`[上标]{.sup}` → `w:vertAlign`）、
母版槽位（`TOC 1..9` + 多级标题编号 + `outlineLvl` + `updateFields`）、
代码块背景与边框（config 的 `background`/`border` → `w:shd` / `w:pBdr`）、
`\begin{code:lang}` 与 `\begin{caption}`（→ **Caption** 样式）。

**W2 已实现**：数学引擎（LaTeX → MathML → OMML，`engine`/`on_fail`/`xsl` 可配，
行内与块级公式都走同一引擎，块级公式居中且不带首行缩进）。

**W3 已实现**：题注（书签 + `SEQ` 域 + Caption 样式）、交叉引用（`REF` 域）、
`[[toc]]`（TOC 域）、公式编号（无边框三列表格）、编号映射显式化、`E5004`/`E4001` 校验。

**W4 已实现**：表格（三线表/网格/无框、重复表头、固定列宽、GFM 列对齐、合并）、
图片尺寸与对齐（`[[img:path width=2cm align=center]]` + `[image]` 默认值）、
脚注（`[[fn:文字]]` → 注入 `word/footnotes.xml`，正文 `w:footnoteReference` +
页脚 `w:footnoteRef`，**编号由 Word 自动生成**）。

**W5 已实现**：分节（`[[sections]]` → 纸张/页边距/分节符）、页码体系
（`w:pgNumType` 格式 + 重启 + 页脚 `PAGE` 域）、页眉页脚（每节独立、`is_linked_to_previous=False`）、
页面垂直对齐（每节**显式** `w:vAlign`：封面 `center`、正文 `top`）。

**W6 部分的实现**：`[output]` 输出与日志系统、`docgen bug-report`、
`scripts/setup.sh`（自动选可用软件源）与 `scripts/package.sh`（打源码测试版）、
三份面向使用者的文档（QUICKSTART / LIMITATIONS / FEEDBACK）。

**仍未实现**：`docgen init --preset` 预设库、`docgen format`、
视觉回归（LibreOffice headless 对比）、公式图片降级（matplotlib）。
完整清单见 [LIMITATIONS.md](../LIMITATIONS.md)。

## 三个容易被误判为缺陷的行为

### 表格边框：三线表**本来就没有竖线**

`[table] style` 的取值与外观：

| 取值 | 框线 |
|---|---|
| `three_line`（**默认**） | 顶线 + 表头下线 + 底线，**无竖线、无内部横线**（学术三线表） |
| `grid` | 四周框线 + 全部内部横竖线 |
| `none` | 完全无框线 |

看到「只有表头上下和整表上下有框线」时，那是 `three_line` 的**设计如此**；
要竖线请显式设 `style = "grid"`。见
[examples/features/content.md](../examples/features/content.md) 的两种样式对照。

### 标题自动编号（可关）

标题的 `1` / `1.1` 由 `[document] heading_numbering` 控制，**默认开启**：

```toml
[document]
heading_numbering = true    # 默认：H1 → "1"、H2 → "1.1"
heading_numbering = false   # 关闭：标题不再自动编号
```

> ⚠️ **标题文字里不要自己写序号**。`# 1 概述` 叠加自动编号会变成
> `1 1 概述` 的观感（H2 则是 `1.1 1. 概述`）。要么去掉手写序号，要么关掉自动编号。
>
> 关闭编号**不影响** `outlineLvl`：目录域与导航窗格照常工作。

### 标题缩进（可配）

自动编号**自带缩进**（Word 多级列表默认行为）：编号定义与 `HeadingN` 样式里都写了
`w:ind left=720 hanging=360`，所以一级标题并不贴左。要改由 `[document] heading_indent` 控制：

```toml
[document]
# 不写        → 默认 left=720 twips + hanging=360（每级递增）
heading_indent = false                       # 取消缩进，标题齐头
heading_indent.left = "1cm"                  # 自定义距离（支持 cm/mm/in/pt/px/twips）
heading_indent.leftChars = 200               # 按“字符”缩进（中文排版更直观）
heading_indent.firstLineChars = 200          # 首行缩进（与 hanging 互斥）

[styles.heading1]                            # 只改某一级
indent = false
```

| 写法 | 结果 |
|---|---|
| 不写 | `left=720 twips` + `hanging=360`（原行为，向后兼容） |
| `heading_indent = false` | 无 `w:ind`，标题贴左 |
| `heading_indent.left = 0` | 同上（等价写法） |
| `left = "1cm"` / `leftChars = 200` | 按给定值缩进 |
| `[styles.headingN] indent = ...` | 覆盖该级的 `[document]` 设置 |

> 缩进**同时**写在编号定义与样式上：样式级 `w:ind` 优先于编号的 `w:pPr`，
> 这样「取消缩进」不依赖 Word 是否采纳编号定义。
> `firstLine` 与 `hanging` 在 schema 里互斥，同时给出时自动丢弃 `hanging`。

### 脚注（自动编号）

`[[fn:文字]]` 生成 **Word 原生脚注**（不是上标文字）：正文处是
`w:footnoteReference`，页脚处是 `w:footnoteRef` —— 两者都由 **Word 自动编号**，
插入/删除/重排脚注时编号会自己更新。

> ⚠️ 两个容易踩的坑（都已修，有回归测试）：
> 1. 条目里缺 `w:footnoteRef` → 页脚**不编号**，只显示文本；
> 2. `vertAlign=superscript` 加在**整条脚注文本**上 → 脚注正文整体变上标。
>    正确做法是只加在**编号 run** 上（`FootnoteReference` 字符样式）。

脚注行距**默认单倍**（`w:line=240`），不跟随正文的 `line_spacing`——
否则正文设 1.4 倍时脚注区会显得很松。要改：

```toml
[styles.footnote]
line_spacing = 1.5    # 倍数；不写则 1.0
```

分隔符条目用 `w:separator` / `w:continuationSeparator` **元素**
（不是 `w:br w:type="separator"`——那个取值非法，会被 schema 判错）。

### `---` 分隔线是段落底边框

渲染成「空段落 + `w:pBdr/w:bottom`」，线段样式可配：

```toml
[document]
hr.style = "single"     # single / double / dashed / dotted / wave …
hr.color = "808080"
hr.size = "6"           # 八分之一磅为单位
```

**不会**再输出 `————————` 这种破折号串（那样复制、检索、改字号都会出问题）。

## 分节 / 页码 / 页眉页脚（W5）

```toml
[[sections]]
page.size = "A4"                  # A4 / A3 / A5 / Letter / Legal
page.margin.top = 2.5             # 单位 cm
numbering.format = "upperRoman"   # decimal / upperRoman / lowerRoman / upperLetter
cover = true                      # 页面垂直居中（封面）

[[sections]]
numbering.format = "decimal"
numbering.start = 1               # 正文页码重启
header.text = "DocGen 报告"
footer.text = "第 PAGE 页"         # PAGE 会变成页码域
```

**内容怎么分到各节**：正文里写 `[[sectionbreak]]` 切到下一节。

```markdown
# 实验报告

学号：…　姓名：…　班级：…

[[sectionbreak]]

# 一、实验目的
```

上面这份内容 + 上面的 config = 封面节（标题/署名，垂直居中、罗马页码、无页脚）
+ 正文节（Decimal 页码从 1、有页眉页脚）。

> ⚠️ **不写 `[[sectionbreak]]` 时**沿用旧行为：一次性建好所有节，
> 内容全部落在最后一节，前面是空页。这时 `cover = true` 只表示「这一节页面垂直居中」，
> 不会凭空产生封面内容——早期就是这里让人以为「空白封面」是 bug。

| 能力 | 实现 |
|---|---|
| 分节 | 第 1 条配置作用于已有节；有 `[[sectionbreak]]` 时按需建后续节 |
| 页码 | `w:pgNumType` 的 `w:fmt` / `w:start`；页脚里的 `PAGE` 域 |
| 页眉页脚 | 每节独立设置（`is_linked_to_previous = False`），避免继承错乱 |
| 封面 | `sectPr` 的 `w:vAlign val="center"`（不是段落 spacing） |

**Word 实测**（`examples/minimal/output.docx`）：节 2、页眉「DocGen 演示文档」、
页脚「第 1 页」、标题自动编号 `1 / 1.1`、`SEQ 图 => 1`、`REF fig:1 => 1`、`REF eq:main => (1)`。

## 测试

- [tests/test_ooxml_probe.py](../tests/test_ooxml_probe.py)：OOXML 语义探针
  （样式槽位、`outlineLvl`、四个字体属性、`firstLineChars`、`updateFields`、
  分页符、表格边框、`config 值 == 输出属性` 不变量、确定性输出、图片嵌入）。
- [tests/test_ooxml_validity.py](../tests/test_ooxml_validity.py)：**结构校验**（见下节）。
- [tests/test_ooxml_schema.py](../tests/test_ooxml_schema.py)：**官方 schema 硬校验**（见下节）。
- **不做全文 `document.xml` 快照**（手册 §10.1：属性顺序与库版本差异会让它脆弱）。

## 两层校验

| 层 | 工具 | 能抓什么 |
|---|---|---|
| 结构 | [render/ooxml_check.py](../src/docgen/render/ooxml_check.py) 的手写规则 | `w:p` 下挂了 `w:fldChar`、空 run、表格层级 |
| **schema** | 同上 `validate_with_schema()` + 官方 `wml.xsd` | 子元素**顺序**、属性拼写、必需属性缺漏 |

**为什么需要 schema 这一层**：OOXML 的属性容器是 `xsd:sequence`，
顺序错了 Word **静默忽略**——不报错、也看不出来。手写规则只覆盖了少数几条，
schema 是完整判据。随附的 schema 与用法见
[tests/schemas/README.md](../tests/schemas/README.md)。

| schema 抓到的真实缺陷 | 后果 |
|---|---|
| `w:firstLineChars` / `w:beforeLines` 写成了子元素 | 它们其实是 `w:ind` / `w:spacing` 的**属性** → 首行缩进与段前段后**从未生效** |
| `w:pgNumType` / `w:vAlign` 在 `w:sectPr` 里位置错 | 页码格式与封面垂直居中可能被忽略 |
| `w:tblLayout` / `w:tblBorders` 在 `w:tblPr` 里位置错 | 固定列宽失效 → 表格被内容撑开 |
| `w:left` 排在 `w:tblBorders` 的 `w:bottom` 之后 | 左边框被丢弃 |
| 根元素残留 12 个无用命名空间 + `mc:Ignorable` | 严格消费者报错 |

因此渲染层的所有「加一条属性」都走
[`ooxml.insert_child()`](../src/docgen/render/ooxml.py)：它按 `CHILD_ORDER`
（由 schema 反推）找到正确插入位置，而不是 `append`。

## 结构校验器（防「Word 打不开」）

「XML 合法」不等于「Word 能打开」。实测踩到的坑：`w:fldChar` / `w:instrText` / `w:t`
直接挂在 `<w:p>` 下时 XML 解析完全正常，但 **Word 会直接拒收整份文档**。
[render/ooxml_check.py](../src/docgen/render/ooxml_check.py) 用「允许的子元素」表检查这类问题：

| 检查 | 说明 |
|---|---|
| `w:p` 的子元素 | 只允许 `w:r` / `w:hyperlink` / `w:bookmarkStart` … |
| 域元素位置 | `w:fldChar` / `w:instrText` / `w:t` 必须在 `w:r` 里 |
| `w:pPr` / `w:rPr` 顺序 | 必须是父元素的第一个子元素 |
| 表格结构 | `w:tbl` → `w:tr` → `w:tc` |
| 空 `w:r` | 报出来（清空单元格时的残留） |

**验收方式**：`tests/test_ooxml_validity.py` + 用 Word COM 实际打开。本机已实测示例可被
Word 打开（49 段落 / 19 域 / 3 书签），域更新后结果正确：
`SEQ 图 => 1`、`REF fig:1 => 1`、`REF eq:main => (1)`、标题自动编号 `1 / 1.1 / 1.2`、目录已填充 7 条。

## 渲染核对（视觉验收）

**用 Word 导出 PDF 再渲染**，不要只看 bundled LibreOffice 的排版：

```powershell
# Word COM：导出 PDF（权威排版）
$doc.ExportAsFixedFormat("out.pdf", 17)
# 再用 bundled pdfium 渲染成图
node <libreoffice-kit>/lib/cli.js render --input out.pdf --output-dir preview --pages 2,3 --dpi 110
```

**踩过的坑**：bundled LibreOffice 渲染 docx 时**忽略右页边距**，正文与表格看起来会「排到
页面右边界之外」。用**纯 python-docx 手写的最小对照文档**（显式 `Cm(2.5)` 页边距）渲染，
现象完全相同 → 这是渲染器的局限，不是产出缺陷。同一份 docx 经 Word 导出 PDF 后测得
左右页边距都是 2.5cm（910px 页宽下各约 110px），排版正确。

**结论**：`w:tblW` / `w:tblLayout` / `w:gridCol` 的宽度口径就是「页面宽 − 左右页边距」，
不要为了迁就 LibreOffice 额外扣 `w:tblCellMar`——那会让表格明显偏窄。

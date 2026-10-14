# Changelog

本文件记录 DocGen 的对外可见变化（剪枝版 + 完整版 Word 后端）。格式参考
[Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循
[语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### 新增（标题缩进可配）

- 自动编号自带缩进（`w:ind left=720 hanging=360`，写在编号定义与 `HeadingN` 样式上），
  现在由 `[document] heading_indent` 控制：`false` 取消缩进、`left = "1cm"` 自定义、
  `leftChars`/`firstLineChars` 按字符、`[styles.headingN] indent` 按级覆盖
- 长度支持 `cm`/`mm`/`in`/`pt`/`px` 与纯 twips；`firstLine` 与 `hanging` 互斥（按 schema 丢弃 hanging）
- 样式级 `w:ind` 优先于编号的 `w:pPr`，所以「取消缩进」不依赖 Word 是否采纳编号定义

### 修复（脚注：不编号 + 整条上标）

- **脚注不自动编号**：条目里缺 `w:footnoteRef`（Word 的编号占位），页脚只显示文本。
  现在正文用 `w:footnoteReference`、页脚用 `w:footnoteRef`，**编号完全交给 Word**
  （插入/删除/重排会自动更新）
- **脚注正文整条变上标**：`vertAlign=superscript` 原本加在整条文本 run 上，
  现已只加在**编号 run**（`FootnoteReference` 字符样式）
- **脚注行距偏大**：默认单倍（`w:line=240`），不再跟随正文 `line_spacing`；
  可用 `[styles.footnote] line_spacing` 覆盖
- 分隔符条目改用 `w:separator` / `w:continuationSeparator` **元素**——
  原先的 `w:br w:type="separator"` 取值非法，被官方 schema 抓到

### 新增（Output 系统）

- 新增 [`output.py`](src/docgen/output.py)：日志级别是**阈值**（`log` < `warn`(默认) < `err`），
  `none` **完全静默打印（连结果也不打印）但不静默退出码**；
  `-q` 与 `none` 的区别：`-q` 只收诊断、结果照常，`none` 什么都不打印
- **结果走 stdout、诊断走 stderr**（`check --json` 时 stdout 只有 JSON）
- `[output] level` / `logfile` / `logfile_level`：logfile 默认关闭、**覆盖写**、单文件无滚动，
  头部含 docgen/python/平台/config/input，尾部含退出码；环境变量里的
  `*_TOKEN`/`*_PASSWORD` 等敏感键被过滤
- CLI 全局开关 `-q/--quiet`（终端 err）、`-v/--verbose`（终端 log）、`--logfile PATH`
  ——**只影响终端**，不改文件内的级别
- 新增 `docgen bug-report --output report.txt [-c config]`：打包环境 + config 摘要 + 退出码，
  作为用户报错时的出口

### 新增（table 默认值提示）

- 保持默认 `three_line` 不变；当 **config 未声明 `[table] style` 且内容含表格**时，
  每次构建向 stderr 打一次 **warn 级**提示：
  `[warn] 表格使用默认三线表样式。如需网格：style = "grid"；无框线：style = "none"。`
  显式声明（哪怕仍是 `three_line`）后不再提示；`-q` 下随 warn 一起被收起

### 新增（`[inline]` 映射段）

- `[inline]`：语义名（`strong`/`em`/`strike`/`sup`/`sub`）→ 样式名，**默认同名**，
  不写该段行为完全不变；可重定向，如 `sup = "sup_caret"` 配合 `[styles.sup_caret]`
- 映射在**渲染与校验层**解析，IR 仍保留语义名（解析器不依赖 config）
- 重定向后缺目标样式时报 `E1003`，错误信息**暴露映射链**：
  `^上标^ 或 [文字]{.sup} 映射到 sup_caret（来自 [inline].sup），但 config 缺少 [styles.sup_caret]`
- 样式树里同时保留语义名别名（HTML 侧按名查表也能命中）

### 修复（表格单元格内 inline code 灰底）

- 行内代码此前**没有底纹**；现在统一由 `_render_inline_code` 渲染，
  段落与**表格单元格**内都画 **run 级** `w:rPr/w:shd`
  （不是段落底纹——那样会涂满整行、看着像代码块）
- 默认 `F2F2F2`，可用 `[code_block] inline_background` 改色、`= ""` 关闭

### 修复（用户实测报告的三项行为异常）

- **`---` 输出成一长串破折号**：原来输出 `"———" * 8`，产物里就是字面破折号
  （复制、检索、改字号都会出问题）。现在渲染成**空段落 + `w:pBdr/w:bottom`**，
  线段样式可配：`[document] hr.style` / `hr.color` / `hr.size`
- **标题自动编号不可关**：新增 `[document] heading_numbering`（默认 `true`）。
  关闭后 `HeadingN` 不再绑 `numPr`，但 **`outlineLvl` 保留**，目录与导航窗格照常工作。
  另外明确「标题文字里不要自己写序号」——`# 1 概述` 叠加自动编号会变成 `1 1 概述`
- **页面垂直对齐改为每节显式设置**：封面写 `w:vAlign val="center"`、正文写 `val="top"`，
  不再依赖「python-docx 克隆上一节 sectPr 后再把 `vAlign` 删掉」这种隐含流程

### 修复（顺带发现）

- **`w:color="AUTO"` 是非法值**：`set_paragraph_border` 把颜色统一转大写，
  但 `w:ST_HexColor` 只认小写 `auto`——新增 `_border_color()` 保留小写（由 `test_ooxml_schema` 抓到）
- **`[document]` 里的点号键取不到值**：`hr.style = "double"` 这类点号键在
  `[document]` 中**不会**展开成嵌套表，原来只查嵌套路径 → 配置被静默忽略；
  新增 `Config.setting()`，扁平键与嵌套表两种写法都支持
- 特性矩阵去掉标题里手写的序号（否则与自动编号叠加成 `1.1 1. xxx`）

### 新增（特性矩阵示例 + 每特性一条断言）

- 新增 [`examples/features/`](examples/features)：**每个特性一行、独立信号值**的调试样例
  （粗体/斜体/删除线/下划线/颜色/字号/链接/公式/代码块语言色/表格单元格格式/题注/脚注/分节…），
  一眼看出哪个特性失效，见 [README](examples/features/README.md)
- 新增 [`tests/test_feature_matrix.py`](tests/test_feature_matrix.py)：**每个特性一条断言**，
  矩阵里哪条红就是哪个特性没生效（含两层校验与 HTML 侧）

### 修复（用户实测报告：链接 / 语言变体色 / 表格单元格格式）

- **链接不是真超链接**：原来只给文字加下划线，点不动、也没有关系项。
  现在写正式的「关系项 + `<w:hyperlink r:id>`」两件套（外链 `TargetMode="External"`），
  并套用 Word 默认超链接色 `0563C1`
- **`[code_block.<lang>]` 配置永不生效**（两个独立缺陷叠加）：
  1. `_code_blocks_of` 把点号键展开出的 `code_block.font` **误判成语言变体** `font`，
     导致基座的 `font.name`/`font.size` 凭空丢失；
  2. `build_style_table` 把语言变体登记成裸键 `python`，而渲染层查的是
     `code_block.python` —— 名字对不上，配置永远读不到
  另外语言的合并由「浅合并」改为**深合并**（`config.deep_merge`），
  否则变体的 `font.color` 会被基座的 `font` 整个覆盖
- **表格单元格格式丢失**：单元格原来被拍平成纯文本，`**粗体**` 显示为字面量。
  IR 的 `Table` 新增 `cell_nodes`（与 `rows` 同形状的行内 IR），
  Word/HTML 两侧都按行内节点渲染 → 单元格里的加粗、行内代码、公式、链接都保留
- **`sup`/`sub` 丢掉 config 样式**：`_render_styled` 对上下标提前 `return`，
  `[styles.sup]`/`[styles.sub]`（如字号）被整段丢弃
- **`font.underline` 未实现**：config 声明了却不生效，现已支持（`w:u`）
- **HTML 产出废声明**：Word 口径的嵌套表被硬编码进 CSS，产出
  `style="font: {'bold': True}; font-weight: bold"`；CSS 层现在跳过 `font*` 嵌套键
- **示例库补上内置样式**：`examples/minimal` 与 `examples/features` 现在都声明
  `[styles.strike]`/`[styles.sup]`/`[styles.sub]`（原来缺 `strike`，
  `~~删除~~` 写了却看不到效果）；`docs/config.md` 强化说明
  「Markdown 语法用的是**内置样式名**，不声明就没有格式」

### 新增（官方 OOXML schema 硬校验，学习借鉴 python-docx）

- 随附 ECMA-376 / ISO-IEC 29500 的 WordprocessingML schema 于
  [`tests/schemas/ecma-376/`](tests/schemas/ecma-376)（取自 python-docx 的 `ref/xsd`，
  说明见 [tests/schemas/README.md](tests/schemas/README.md)）
- 新增 `ooxml_check.validate_with_schema()`：用官方 `wml.xsd` 校验 `document.xml`
  （schema 编译 0.1s 并缓存），配 [`tests/test_ooxml_schema.py`](tests/test_ooxml_schema.py) 16 项
- 新增 `ooxml.insert_child()` + `CHILD_ORDER`：**按 schema 顺序**插入属性元素。
  OOXML 的属性容器是 `xsd:sequence`，顺序错了 Word 会静默忽略——
  之前全部用 `append`，产出的 `w:pPr` / `w:sectPr` / `w:tblPr` / `w:tcPr` 顺序不合法

### 修复（schema 校验发现的结构缺陷）

- `w:pgNumType` / `w:vAlign` 在 `w:sectPr` 里位置错（`vAlign` 必须排在 `docGrid` **之前**）
- `w:tblLayout` / `w:tblBorders` 在 `w:tblPr` 里位置错（`tblLayout` 在 `tblCellMar` 之前）
- `w:left` 在 `w:tblBorders` 里排到了 `w:bottom` 之后（schema 顺序是 `top, start, left, bottom, …`）
- **`w:firstLineChars` / `w:beforeLines` / `w:afterLines` 被当成独立元素**——
  它们其实是 `w:ind` / `w:spacing` 的**属性**，写成子元素 Word 直接忽略，
  等于「首行缩进、段前段后」这条排版细则此前**根本没生效**
- 根元素残留 12 个未使用的命名空间声明与 `mc:Ignorable`（严格 schema 会报错），
  现按「前缀是否真的被用到」清理
- 测试假阳性修正：`test_formula_renders_as_omml` 原来断言文档里含 `"mc"`，
  而 `"mc"` 来自公式内容 `E = mc^2`——已改为断言 `<m:oMath` 与 `xmlns:m=`

### 修复（渲染核对 / Word 实测发现）

- **表格宽度写不进去**：`add_table(rows, cols)` 的 `cols` 决定的是**行内 `w:tc` 数量**，
  而列宽写在 `w:tblGrid` 上——之前按 3 列算宽度、grid 只有 2 列，表格宽度对不上。
  现在统一 `_fit_grid()` 对齐列数，并写全 `w:tblW` + `w:tblLayout fixed` + 每列 `w:gridCol`，
  防止 Word 按内容重算列宽把表格撑开。
- **封面垂直居中泄漏到正文节**：python-docx 的 `add_section()` 会**克隆上一节的 `sectPr`**，
  于是 `w:vAlign val="center"`（封面专用）跟到了正文节。现在非封面节显式删除该元素。
- **`stylesWithEffects.xml` 里的 `Courier`**：默认模板的该部件完整复制了一份样式表，
  删掉 `MacroText` 后仍会报「缺少字体」；现在构建时删除该部件并同步清理内容类型。
- **`rsid` 噪声**：母版带来的 `w:rsidR/RPr/Sect` 对生成文档无意义，构建时清掉。
- **渲染口径澄清**：bundled LibreOffice 渲染 docx 时**忽略右页边距**
  （用纯 python-docx 手写对照文档验证过，同样现象），因此视觉核对改用
  **Word 导出 PDF**（`ExportAsFixedFormat`）+ pdfium 渲染。Word 实测：A4 左右页边距
  均为 2.5cm（渲染 109–117px / 910px 页宽），表格、页眉页脚、域结果全部正确。

### 新增（完整版 W5：分节 / 页码 / 页眉页脚 / 封面）

- **分节**：`[[sections]]` 配置纸张（A4/A3/A5/Letter/Legal）、页边距（cm）、分节符
- **页码体系**：`numbering.format`（decimal / upperRoman / lowerRoman / upperLetter）
  与 `numbering.start`（重启）→ `w:pgNumType`；页脚里的 `PAGE` 变成页码域
- **页眉页脚**：每节独立（`is_linked_to_previous = False`），避免 Word 继承错乱（§17.1）
- **封面**：`cover = true` → `sectPr` 的 `w:vAlign val="center"` 垂直居中

### 新增（完整版 W4：表格 / 图片 / 脚注）

- **表格**：`[table] style` 三线表/网格/无框、`header_repeat`（`w:tblHeader` 跨页重复表头）、
  `col_widths` 固定列宽（比例归一化）、GFM 列对齐（`:---:`）、IR `TableCell` 合并
  （`w:gridSpan` / `w:vMerge`）
- **图片**：`[[img:path width=2cm align=center]]` 与 `[image]` 默认值，支持 `cm/mm/in/px/pt`
- **脚注**：`[[fn:文字]]` → `Footnote` 行内节点 + **手写 `word/footnotes.xml`**
  （含 `separator`/`continuationSeparator` 条目）+ 内容类型与关系项注入
- IR 新增 `TableCell` / `Footnote`，`ImageBlock` 增加 `width`/`align`；
  config 新增 `extra` 命名空间（`[table]`/`[image]`/`[math]`/`[[sections]]`）

### 修复（Word 打不开 / 域结果错误，均由 Word 实测发现）

- **Word 报「无法打开文件」**：`w:fldChar` / `w:instrText` / `w:t` 被直接挂在 `<w:p>` 下，
  而 OOXML 要求它们必须包在 `<w:r>` 里。涉及题注 `SEQ` 域、引用 `REF` 域、目录 `TOC` 域；
  已在 [ooxml.py](src/docgen/render/ooxml.py) 统一改成「每个域片段一个 run」。
- **`REF` 域报「错误！未找到引用源」**：公式编号的书签 `start`/`end` 用了**两个不同 id**；
  另外题注书签包住了整条题注，引用取到整段文字而不是编号。现在书签只包编号，
  id 由文档级计数器统一分配（不重复）。
- **空书签**：先插书签再写内容会得到空书签（`REF` 取不到值），改为写完内容再整体包书签。
- **表格单元格残留空 `<w:r/>`**：`cell.text = ""` 会留下空 run，改为删除空 run。
- **字体未登记**：`word/fontTable.xml` 没登记 Consolas/等线等实际用到的字体，
  Word 与预览会提示「缺少字体」并替换字形；新增 `ensure_font_table()` 构建时登记。
- **代码块的中文字体**：原来把 `w:eastAsia` 也设成 Consolas（等宽西文字体），
  中文会掉字体；现在只设西文（`ascii`/`hAnsi`/`cs`），`eastAsia` 留给样式链。

### 新增（Word 产出结构校验器）

- [render/ooxml_check.py](src/docgen/render/ooxml_check.py)：检查「XML 合法但结构非法」的问题
  （域元素必须在 run 内、`w:pPr`/`w:rPr` 顺序、表格层级、空 run）；
  [tests/test_ooxml_validity.py](tests/test_ooxml_validity.py) 覆盖全部特性与真实示例。

### 新增（完整版 W3：编号 / 题注 / 交叉引用）

- **公式编号**：`\begin{equation #eq:main number=1}` → 无边框三列表格（左空 / 中公式 / 右编号），
  编号带书签，可被 `[[ref:eq:main]]` 引用；无 `number` 时就是普通块级公式
- **构建路径与母版路径共用槽位补齐**：`create_document()` 现在也会补 `TOC 1..9`、
  多级编号、题注/脚注样式与 `updateFields`（此前只有 `build_template()` 补，
  导致 `docgen build` 产出的文档缺这些槽位——由验收脚本发现并加回归测试）
- **`sup`/`sub` 纳入内置样式名**：`H~2~O`、`E=mc^2^` 不再被 `check --strict` 误报 `E1003`
- **示例升级**：`examples/minimal` 现在覆盖 W0~W3 全部特性（目录、双语法代码块、
  题注、交叉引用、公式编号、上下标、分页），`check --strict` 通过、docx/html 均可构建
- **DFM 新标记**：`[[ref:目标]]`（`Ref` 行内节点）、`[[toc]]`（`Toc` 块）；
  `\begin{... #id}` 的 `#id` 作为引用目标（`NamedBlock.label`）
- **题注**：带标签的 `caption`/`table`/`equation` 命名块渲染成
  书签 + `SEQ 图 \* ARABIC` 编号域 + **Caption** 样式；题注按类型独立计数（图/表/公式）
- **交叉引用**：`[[ref:fig:1]]` → `REF fig:1 \h` 域；HTML 侧渲染为 `#fig:1` 锚链接
- **目录占位**：`[[toc]]` → `TOC \o "1-9" \h \z \u` 域（配合既有 `updateFields`）
- **编号映射显式化**：`numbering.heading_numbering()` 把 `level -> (ilvl, HeadingN)` 写成一张表
- **校验**：引用目标不存在 → `E5004`；标签重复 → `E4001`；`check --strict` 一并报告

### 新增（完整版 W2：数学渲染）

- **数学引擎**：`render/math.py` 把 LaTeX 经 `latex2mathml` → MathML → Office
  `MML2OMML.XSL` → **OMML**（`m:oMath`），公式在 Word 里可编辑
- `[math]` 配置：`engine = auto|xsl|plain`、`on_fail = plain|error`（`E5002`）、`xsl` 路径；
  也可用环境变量 `DOCGEN_MML2OMML`；找不到 XSL 时自动降级，构建不会挂
- 行内与块级公式共用引擎；块级公式居中且不带首行缩进
- 公式测试集 40 条，转换通率 **40/40 = 100%**（手册验收 > 90%）
- 修复确定性测试：比 `document.xml` 而不是 docx 字节（zip 时间戳不可比）

### 新增（完整版 W1：基础渲染 + 母版槽位）

- **上下标**（手册 §6.2.3）：`H~2~O` / `E=mc^2^`（Pandoc 单字符标记）与
  `[上标]{.sup}` / `[下标]{.sub}`，Word 侧写 `w:vertAlign`
- **母版构建**：`render/template_build.py` 幂等补齐 §14.1 槽位——`TOC 1..9` 样式、
  多级标题编号（`numId=100`，`Heading1`→`1`、`Heading2`→`1.1`）、
  `HeadingN` 的 `outlineLvl` 与 `numPr` 绑定、`updateFields`；
  `tests/test_template.py` 断言全部槽位（CI 重建即验证）
- 文档：`docs/word.md` 补母版与已实现清单；`docs/dfm.md` 补上下标语法

### 新增（完整版 W0：最小 docx 链路）

- **Word 后端**：`docgen build -o out.docx` 与 `--format=docx` 端到端可用
- [render/ooxml.py](../src/docgen/render/ooxml.py)：所有 `OxmlElement` 构造集中一处，
  处理手册 §17.1 的陷阱（四个 `rFonts`、`firstLineChars`、`beforeLines`/`afterLines`、
  `outlineLvl`、`updateFields`）
- [render/template.py](../src/docgen/render/template.py)：母版加载、样式槽位校验、
  标题 `outlineLvl`、`updateFields`
- [units.py](../src/docgen/units.py)：`12pt` / `16px` / `1.5em` / 纯数字 → 磅
- **config 点号键**：`[document] font.name = "宋体"`、`[styles.x] font.bold = true`
  （手册 §6.1 口径），展开后为嵌套表
- **错误码扩展**：`E2010` keywords 非法、`E3002` `\begin` 名字不一致、
  `E5002` 数学转换失败、`E5003` 分节配置、`E5004` 编号/引用不存在
- **OOXML 语义探针**：`tests/test_ooxml_probe.py`（样式槽位、`outlineLvl`、
  四个字体属性、`firstLineChars`、`updateFields`、分页符、表格边框、
  config 值 == 输出属性的不变量、确定性、图片嵌入）
- 文档：[docs/word.md](../docs/word.md)

### 计划中

- 遗留：剪枝版第 5 周可选的临时 HTML → Word 输出（已被正式 Word 后端取代，不再实现）

## [0.1.0] - 2026-10-10

首个可交付版本：`DFM + TOML → HTML` 全链路可用，182 项测试、覆盖率 89%。

### 新增

- **IR**：全部行内/块级节点为 `frozen+slots` dataclass，块级节点带 `source_line`
- **DFM 解析**：标题、段落、嵌套列表、引用、代码块、分隔线、表格、行内/块级数学、
  `[文字]{.样式名}`、`[[img:path]]`、`[[pagebreak]]`；粗体/斜体/删除线统一为 `Styled`
- **config**：`include` 递归合并、`based_on` 单继承（深度上限 8、环检测）、
  `@ref` 跨命名空间解析、`for = false` 软删除
- **语义校验**：样式引用不存在（`E1003`）、图片缺失（`E5001`）
- **诊断**（`check --strict`）：未闭合标记（`E3001`）、未知代码语言（`E2001`）、
  代码围栏未配对（`E4001`）
- **金标准交叉验证**：IR 与 markdown-it token 流的一次性归约做结构等价比较，
  覆盖嵌套列表、引用嵌套、围栏语言、表格行列、公式与自研标记的归一
- **渲染**：IR → HTML（内联样式取 config 展开值，文本与属性 HTML 转义）+ 确定性 CSS
- **CLI**：`dump-ir`、`dump-styles [--raw]`、`check [--json] [--strict]`、`build`
- **示例**：`examples/minimal`、`examples/inherit`
- **文档**：`docs/dfm.md`、`docs/config.md`、`docs/ir.md`、`docs/crosscheck.md`
- **CI**：GitHub Actions 在 Python 3.11/3.12 上跑 ruff / mypy / pytest（覆盖率门槛 70%）

### 约定

- 错误码：`E1001` 循环继承、`E1002` 继承超深、`E1003` 样式/引用不存在、
  `E2001` 未知语言、`E3001` 标记未闭合、`E4001` 语法错误、`E5001` config/文件错误
- 退出码：`0` 成功、`1` 内容错误、`2` 配置/文件错误
- 解析器宽容（未闭合标记退化为字面文本、不丢内容），诊断由 `check` 负责

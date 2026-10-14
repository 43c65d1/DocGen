# Changelog

本文件记录 DocGen 的对外可见变化（剪枝版 + 完整版 Word 后端）。格式参考
[Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循
[语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

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

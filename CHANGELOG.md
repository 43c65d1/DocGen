# Changelog

本文件记录 DocGen 的对外可见变化。格式参考
[Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循
[语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### 新增（浮动图片 / 文字环绕）

- `[[img:path wrap=square]]`：图片从「独占一行的块级对象」变成**浮动图片**
  （`wp:anchor`），文字按环绕方式绕排；`wrap` 支持 `square`（四周型）、
  `top-bottom`（上下型）、`behind`（衬于文字下方）、`front`（浮于文字上方）；
- `align` 控制水平位置（相对页边距），`dist` 设四周留白、`vpos` 设相对段落的
  垂直偏移（都带单位）；`[image] wrap / dist / vpos` 可设全局默认，标记属性优先；
- `anchor` 子元素按 schema 顺序生成（simplePos → positionH → positionV → extent →
  effectExtent → wrap → docPr → graphic），叠放次序逐图递增；
- 非法 `wrap` / `dist` / `vpos` 报 `E5001`；默认（不写 `wrap`）仍是 inline，行为不变；
- 实测：`wrap=square align=right width=2cm` → `wp:anchor` + `wp:wrapSquare`，
  `distT=114300`、`extent cx=720000`；示例文档通过官方 WML schema 校验；
- 已知限制：「紧密型 / 穿越型」的多边形环绕未实现（用 `square`）。
- 新增 `tests/test_floating_images.py`（12 项）。

### 新增（外文作者姓名缩写）

- `[bibliography] western_initials = true`：西文作者自动转 GB/T 7714 的
  「姓前名后、姓大写、名缩写」，`John A. Hewitt` / `Hewitt, John A.` / `Hewitt J A`
  均输出 `HEWITT J A`；支持连字符名（`SARTRE J P`）、姓氏前缀（`VAN DER WAALS J`）、
  后缀（`SMITH J Jr.`）；
- 中文姓名原样保留；与 `author_truncate` / `et_al` 可叠加（先缩写再截断）；
  `author` 为字符串时同样生效；默认关闭，行为不变；
- 已知边界：拼音姓名 `Li Ming` 按西文规则被当成「名 Li、姓 Ming」，需写成 `Li, Ming`；
- 新增 `tests/test_bibliography_names.py`（9 项）。

### 新增（表格逐表宽度）

- 表格里写 `[[table-width:80%]]` / `[[table-width:12cm]]`：只设**这张表**的总宽
  （默认正文宽度），列宽按比例重算；
- 表格里写 `[[col-widths:3,2,5]]` / `[[col-widths:3cm,auto]]`：只设**这张表**的列宽，
  语义与 `[table] col_widths` 相同（比例 / 绝对宽度 / auto 混写）；
- 标记写在任意单元格、不渲染文字、同名取第一个；普通 GFM 表与合并单元格表两条
  渲染路径都生效；
- 带宽度标记的表按固定宽度渲染（`[table] autofit = true` 对它不生效）；
  非法值报 `E5001`；
- 实测：同文档三张表分别为正文宽、80%、`col-widths 1:3`；`tblW` 与 `gridCol` 之和一致；
  合并单元格表 50% 生效。
- 新增 `tests/test_table_width_per_table.py`（10 项）。

### 新增（图注 / 表注）

- `\begin{note}`：图注 / 表注段落，挂「Caption Note」样式（基于 `Caption`：左对齐、
  无首行缩进、字号跟随题注）；**写在哪渲染在哪**——紧跟图题是整图注，放在表格后是表注；
- 写进 `\begin{subfigure}` 内是**图元注**：渲染到该子图单元格的第三行，与各自子图对齐；
- 图题后面紧跟图注时题注自动 `keepNext`、图注自带 `keepLines`，图片 + 图题 + 图注
  不会被分页拆开；表注接在表格后时仍吃 `[table] space_after`；
- `[styles.caption_note]` 覆盖字体类属性（`font.size` / `font.color` …）与段落级属性
  （`alignment` / `space_*`）；图注不进插图清单（清单只取题注第一段）；
- 解包 XML 实测：图注样式 `basedOn=Caption`、`jc=left`、`sz=18`（9pt）；三条注段落均带
  `keepLines`，图题 `keepNext` 且注紧随其后；子图表格 3 行、图元注在第三行；表注在表后。
- 新增 `tests/test_figure_notes.py`（8 项）。


### 新增（B5 / 横向 / 装订线）

- `page.size` 新增 `B5`（17.6 × 25.0 cm）；
- `page.orientation = "landscape"`：横向；按 size 自动交换宽高，同时写
  `w:pgSz/@w:orient`；显式 `page.width/height` 时不再交换（作者给的尺寸就是最终值）；
- `page.gutter = 0.5`：装订线（cm），写 `w:pgMar/@w:gutter`；
- 非法方向 / 装订线值报 `E5003`（分节配置错误）。
- Word COM 实测：B5 横向 708.65 × 498.9pt、Orientation=Landscape、Gutter 14.15pt。
- 新增 `tests/test_section_page.py`（7 项）。

### 新增（可选 Word autofit）

- `[table] autofit = true`：写 `tblLayout autofit` + `tblW auto`，列宽交给 Word 按内容算；
- 与 `col_widths` 互斥（同时设置报 `E5001`，避免「写了不生效」）；
- 默认 `false`，继续用构建期宽度（`col_widths` / `"auto"`），结果确定可测试；
- 文档明确 tradeoff：Word autofit 简单但 Word/WPS/LibreOffice 结果可能不同；
- Word COM 实测：`AllowAutoFit=True`、`PreferredWidthType=Auto`。
- 测试：`tests/test_table_auto_width.py` 增至 7 项。

### 新增（表格自动列宽 / 单行行高）

- `col_widths = "auto"`：构建期按内容估算列宽（CJK 记 2、ASCII 记 1），
  短列自动变窄；`col_widths = ["3cm", "auto"]` 支持绝对宽度与 auto 混用。
  不交给 Word autofit，结果确定、可测试。
- `[[row-height:1.2cm]]`：写在任意单元格里，只设置当前行行高；标记不渲染文字。
  全局/表头仍用 `row_height` / `header_row_height`。
- 非法混合（数字比例 + auto）、无法识别的宽度报 `E5001`。
- Word COM 实测：auto 两列 36pt / 396pt（短列窄）；行高标记只作用于目标行
  （row2 34pt = 1.2cm，row1 未设）。
- 新增 `tests/test_table_auto_width.py`（5 项）。

### 新增（逐单元格边框）

- 表格单元格内标记 `[[border:all]]` / `[[border:top,bottom style=double size=1.5pt color=FF0000]]`：
  给该单元格逐边写 `w:tcBorders`，标记本身不渲染文字；
- 边名支持 `all` 或 `top/left/bottom/right` 组合；线型
  `single/double/dashed/dotted/none`；颜色 6 位十六进制或 `auto`；
- 普通表格与合并单元格表格两条路径都生效；非法值报 `E5001`；
- Word COM 实测：`all style=double size=1.5pt color=FF0000` → 上边框
  LineStyle=Double、宽度 1.5pt、红色；指定 `top,bottom` 时左右为 None。
- 新增 `tests/test_cell_borders.py`（8 项）；LIMITATIONS B15 全部解决并移除。

### 新增（表格单元格内边距）

- `[table] cell_margin`：表格级 `w:tblCellMar`，四边统一（如 `"0.1cm"`）；
- `cell_margin_top/bottom/left/right` 逐边覆盖；
- 不写配置时保留 Word 默认（左右 0.19cm、上下 0），不影响既有文档；
- 非法长度值报 `E5001`；
- Word COM 实测：`cell_margin="0.1cm"` + `left="0.2cm"` →
  LeftPadding 5.65pt、其余 2.85pt。
- 新增 `tests/test_table_cell_margins.py`（5 项）。

### 新增（分节双栏）

- `[[sections]] page.columns`：栏数 1–9；可写简写 `2`，或
  `{ count = 2, space = "0.63cm", separator = true }`（栏间距/分隔线）。
- 每节独立，配合 `[[sectionbreak]]` 可做「前置单栏、正文双栏」；
  IEEE 式双栏正文不再需要生成后手工分栏。
- 非法栏数/间距/分隔线值报 `E5003`（分节配置错误）。
- Word COM 实测：`TextColumns.Count=2`，间距 0.63cm→17.85pt / 0.5cm→14.15pt，
  `LineBetween` 随配置 true/false。
- 新增 `tests/test_section_columns.py`（8 项）。

### 新增（表题同页 / 表格行不跨页）

- 表题写在表格**上方**且 `kind=table` 时，题注段落自动 `keepNext`，与表格绑在同一页；
  题注写在表格下方不绑定（顺序错误应显式改）。
- `[table] rows_keep_together`（默认 `true`）：所有表格行写 `cantSplit`，行内不跨页；
  `false` 时仅表头行保持 `cantSplit`，允许长行拆到两页。
- Word COM 实测：题注 `KeepWithNext=True`；默认所有行 `AllowBreakAcrossPages=False`，
  关闭配置后仅表头为 `False`（其余 `True`）。
- 新增 `tests/test_table_caption_binding.py`（5 项）。

### 新增（子图 / 分图）

- 新增 `\begin{subfigures}` 容器 + `\begin{subfigure #fig:a}` 子图块：
  并排渲染为无边框表格（上行图片、下行 `（a）说明` 子题注）。
- 子编号 a/b/c… 按容器顺序生成；总图题仍由后面的 figure `caption` 负责，
  编号/插图清单/REF 复用现有机制。
- 引用 `图 [[ref:fig:a]]` 烘焙为 `图 1（a）`（按章模式 `图 2-1（a）`）。
  因为书签包的是整段子题注，REF 域更新后会返回说明文字而不是编号，
  所以子图引用改用**静态文本**（与按章题注同一取舍）。
- 子题注支持「图片下一行同一段」与「空行单独一段」两种写法；
  宽度默认 n 张平分正文宽的 90%，`[subfigure] width` 或单图 `width=` 可覆盖。
- 修复：图片未指定 `width` 时，`_add_picture` 会在图片后多输出一段 20 个破折号
  （原先只有指定了合法宽度才提前 return）；现在无宽度图片不再多出空段落。
- 新增 `tests/test_subfigures.py`（5 项）。

### 新增（超链接颜色/下划线可配）

- `[styles.hyperlink]`：`font.color`（默认 Word 蓝 `0563C1`；`auto` = 跟随正文）、
  `underline`（默认开；`"none"` / `"off"` 关闭）。
- 解决「论文要求全文纯黑，但超链接写死蓝色」的缺口；链接仍是真正的
  `w:hyperlink` 关系项，点击可跳转。
- 注意 `underline = false` 不生效：样式层把 `false` 当作“删除继承键”；
  关下划线请写字符串 `"none"`（已在文档中说明）。
- 非法颜色（非 6 位十六进制/`auto`）或非法下划线值报 `E5001`。
- 新增 `tests/test_hyperlink_style.py`（8 项）。

### 新增（`$$...$$` 参与公式编号，opt-in）

- `[math] number_display_math = true` 时，独立 `$$...$$` 与 `\begin{equation}`
  共用同一编号序列（auto 1、2、3… / chapter 2-1）。
- 默认 `false`：`$$...$$` 保持无编号——推导中间式通常不需要编号，
  需要编号/引用时写带 `#id` 的 `\begin{equation}`（`$$...$$` 无标签，不能 `[[ref:...]]`）。
- 开启该开关但 `numbering = "none"` 时明确报 `E5001`（避免「开了却不生效」）；
  非法布尔值同样报错。
- 测试：新增 5 项，`tests/test_formula_auto_numbering.py` 共 19 项。

### 新增（公式自动编号 + 引用）

- `[math] numbering`：`none`（默认，仅 `number=` 手写）/ `auto`（1、2、3…）/
  `chapter`（按一级标题分章，2-1）。
- 只作用于 `\begin{equation}` 命名块（普通 `$$…$$` 仍不编号）；手动 `number=` 优先，
  并把自动计数同步到该值（`number=7` 后下一项为 8）。
- 带 `#id` 的公式自动编号后仍写书签，`[[ref:eq:id]]` 的 `REF` 域缓存值同步为
  真实编号；`baked_fields` 也覆盖自动编号。
- `chapter` 模式下第一个一级标题之前的公式按连续编号（1、2…），不出现 0-1。
- 非法 `numbering` 值报 `E5001`，`docgen check` 同样报出。
- 新增 `tests/test_formula_auto_numbering.py`（14 项）。

### 新增（目录级别）

- `[toc] levels`：控制 `[[toc]]` 只收录到第几级标题，默认 `1-9`；
  可写 `3`（= 1-3）或 `"2-4"`；非法值报 `E5001`，`docgen check` 同样报出。
- TOC 域按配置生成 `\o "1-N"`；Word 更新目录后只出现指定级别的条目（实测 1-2 级）。
- **目录条目样式（TOC 1..9）不可预置**：Word 更新目录时会把这些内置样式重置为
  默认值（实测预置字体/段距会丢失）；已在 LIMITATIONS 新增 B19，需要改样式请在
  Word 里更新目录后手动调整。
- 新增 `tests/test_toc_levels.py`（11 项：默认/整数/区间/非法值/仍为 TOC 域）。

### 新增（插图清单 / 附表清单）

- 新增 `[[list:figures]]` / `[[list:tables]]`：按全文题注自动生成
  「图/表编号 + 题注文字 + `PAGEREF` 页码域」，右对齐点线制表位。
- `[list]` 配置：`figures` / `tables`（标题，默认「插图清单」「附表清单」）、
  `heading_level`（1–9，用 Heading N 样式但取消编号）；非法值报 `E5001`。
- 与题注编号模式联动：连续编号显示「图 1」，`caption_numbering = "chapter"`
  显示「图 2-1」；清单可放在正文任意位置。
- 页码是 `PAGEREF` 域：Word 打开时随 `updateFields` 计算；不更新域的预览
  显示占位 1（与目录/页码同一类限制，已补进 LIMITATIONS B13）。
- Word COM 实测：两页文档中「插图清单」条目页码更新后为 1 / 2，
  附表清单为 1，标题为无编号 Heading 1，文档正常打开。
- 新增 `tests/test_caption_lists.py`（11 项）。

## [0.1.0b2] - 2026-11-15

### 新增（表格布局与合并语法）

- **行高**：`[table] row_height`（如 `"0.8cm"` / `"20pt"`）、`header_row_height`
  （表头单独设）、`row_height_rule`（`atLeast` / `exact` / `auto`）。
- **按厘米列宽**：`col_widths = ["3cm", "5cm"]`（绝对宽度）；数字数组仍按比例。
- **单元格垂直居中**：`cell_vertical_align = "top" / "center" / "bottom"`。
- **DFM 合并语法**：表格单元格里写 `[[merge:2]]`（横并 2 列）、
  `[[merge:1,2]]`（纵并 2 行）、`[[merge:2,3]]`（2 列 × 3 行）；
  横并后的占位格与纵并续行的占位格按网格列补空即可。
- **合并渲染修正**：改用 python-docx `cell.merge()` 真正合并（正确的
  `w:gridSpan` / `w:vMerge`），不再只写属性却留着重复 `w:tc`。
- Word COM 实测：表头 1cm/正文 0.8cm 行高（atLeast）、3cm/5cm 列宽、
  单元格垂直居中；3×3 表格横并 + 纵并后 Word 识别为合并区域，文档正常打开。
- 测试：`tests/test_table_layout.py`（9 项）+ `tests/test_table_merge_syntax.py`（9 项）。

### 新增（页眉页脚增强）

- **奇偶页不同**：`header.odd.text` / `header.even.text`（footer 同理），
  自动打开文档级 `w:evenAndOddHeaders`。
- **首页不同**：`header.first.text` / `footer.first.text`，自动设置该节 `titlePg`。
- **页眉底部线**：`header.line = "double"` 映射到 OOXML `thickThinSmallGap`
  （粗线在上、细线在下）；也支持 `single` / `thinThickSmallGap` / `dotted` /
  `dashed` / `none`，线宽 `line_size`、线色 `line_color` 可配。
- **字体**：`header.font.name`（中文）/ `font.latin`（西文）/ `font.size`
  （支持 `小五` 等中文字号）/ `font.color` / `font.bold` / `font.italic`；
  `PAGE` 域同样套用字体。
- **对齐/距边界**：`header.alignment`（left/center/right）、
  `header.distance` / `footer.distance`（cm）。
- 非法配置（对齐、线型、距离）报 `E5003`。
- Word COM 实测：奇数页「第一章 论文题目」/ 偶数页「XX大学硕士学位论文」，
  9pt 宋体、居中、底部 thickThinSmallGap 线（1.5pt），页眉距边界 1.5cm、
  页脚 1cm，页脚「第 1 页」，文档正常打开。
- 新增 `tests/test_header_footer_rich.py`（9 项）。

### 新增（图/表按章编号）

- `[document] caption_numbering = "chapter"`：图/表编号变为「章号-序号」
  （图 2-1、表 2-1），以一级标题（Heading 1）分章；默认 `continuous`
  保持原行为（图 1、图 2）。第一个一级标题之前的题注不加章号前缀。
- 按章模式题注编号写成**静态文本**（不再用 `SEQ` 域）：`SEQ` 只给章内整数，
  更新域会把「2-1」改回「1」；书签仍包住编号，`[[ref:...]]` 的 `REF`
  取到的也是「2-1」。
- 与 `heading_numbering` 预设联动无关（章号按一级标题顺序算）：
  `heading_numbering = "chapter"` + `caption_numbering = "chapter"` 可同时用。
- 非法取值报 `E5001`，`docgen check` 同样报出。
- Word COM 实测（Fields.Update 后仍稳定）：第一章 绪论 / 图 1-1 / 表 1-1 /
  图 1-2 / 第二章 方法 / 图 2-1 / 表 2-1，REF 显示 1-1，文档正常打开。
- 新增 `tests/test_caption_chapter.py`（16 项：模式解析、编号分配、
  章前题注、静态文本/书签、与标题预设组合、公式不受影响、非法值）。

### 新增（标题中文编号格式）

- `[document] heading_numbering` 从布尔开关扩展为预设：
  `decimal`（默认，1 / 1.1 / 1.1.1，Word 多级编号）、`chapter`
  （第一章 / 1.1 / 1.1.1）、`chinese`（一、 / （一） / 1. / （1））；
  仍支持 `false` 关闭与 `heading_numbering.enabled = false`。
- `chapter` / `chinese` 改为**构建期烘焙文本**：标题段落写死编号并清掉样式 numPr，
  不会出现「1 第一章」双重编号；TOC/预览也能直接看到编号。
- 非法预设报 `E5001`，`docgen check` 同样报出。
- Word COM 实测：`第一章 绪论` / `1.1 研究背景` / `1.1.1 问题定义` / `第二章 方法`，
  ListString 为空（无重复编号），文档正常打开。
- 新增 `tests/test_heading_numbering_format.py`（18 项：模式解析、编号文本、
  层级重置、两种预设渲染、默认/关闭行为、非法值）。

### 新增（参考文献表规范化）

- **条目编号**：参考文献表条目现在默认带 `[n]` 前缀（顺序编码制要求）。
  此前条目只有正文、没有序号，属实现缺陷；可用 `[bibliography] entry_number = false` 关闭。
- **悬挂缩进**：`[bibliography] hanging_chars = 2`（字符数），按正文字号换算；
  同时写 `w:hangingChars` 与数值版 `w:left`/`w:hanging`，WPS/旧版 Word 兼容。
- **引用上标**：`citation_superscript = true` 时正文 `[[cite:...]]` 显示为上标。
- **作者截断**：`author_truncate = 3` 时作者数组超过 3 名截断为「前 3 名 + 等/et al.」；
  中文自动用「等」、西文用「et al.」，`et_al = "..."` 可覆盖。3 名以内不截断；
  字符串形式的 `author` 不截断（无法安全拆分）。
- 非法设置（负数、非整数、非布尔）报 `E5001`，`check` 也会报出。
- Word 实测：条目显示 `[1] 张三, 李四, 王五, 等. …`、悬挂缩进 2 字符、
  正文引用上标，文档正常打开。
- 测试：`tests/test_bibliography.py` 新增 9 项（共 28 项）。

### 新增（中文字号：号数制换算）

- `font.size` 现在接受**中文字号**：`"小四"`（12pt）/ `"三号"`（16pt）/ `"五号"`（10.5pt）
  等，写 `"小四号"` 也认；`[document]` / `[styles.*]` / `[table.text]` 均生效。
- 换算表按 Word/WPS 同口径（也是高校规范的「三号/小四」含义）：
  初号 42 / 小初 36 / 一号 26 / 小一 24 / 二号 22 / 小二 18 / 三号 16 / 小三 15 /
  四号 14 / 小四 12 / 五号 10.5 / 小五 9 / 六号 7.5 / 小六 6.5 / 七号 5.5 / 八号 5（pt）。
- 顺带修复：非法字号（如 `"小十"`）此前抛未捕获 `ValueError`，现在报 `E5001`
  并列出支持写法；`pt` / `磅` / `px` / `em` / `rem` 与纯数字行为不变。
- Word COM 实测：正文 12pt、标题 16pt、表格 10.5pt 全部正确，文档正常打开。
- 新增 `tests/test_cn_font_sizes.py`（41 项，含全部映射与四种作用域的渲染）。

### 新增（固定行距 + 中西文字体分离）

- **行距固定值**：`line_spacing` 现在区分两种语义——数字 = 倍数（`1.5`），
  `"20pt"` / `"20磅"` = **固定磅值**（`w:lineRule="exact"`）；`[document]`、
  `[styles.*]`、`[table.text]` 全部生效。
- **修复崩溃**：此前 `line_spacing = "20pt"` 会抛未捕获的
  `ValueError: could not convert string to float`（CLI traceback）；现在统一解析，
  非法值报 `E5001` 并给出写法提示。`docs/manual.md` 里「`"20pt"` 按倍数」的错误说明已更正。
- **中西文字体分离**：新增 `font.latin`（src: ascii/hAnsi/cs）。`font.name` 保持中文
  （eastAsia）语义；只写 `font.name` 时西文也用它（旧行为不变）。
  `[document]` / `[styles.*]` / `[table.text]` 均支持。
- Word COM 实测：正文 `lineRule=exact` 20 磅、表格 18 磅；西文 Times New Roman、
  中文 SimSun/SimHei 各自生效，文档正常打开。
- 新增 `tests/test_line_spacing.py`、`tests/test_font_latin.py`（27 项）。

### 新增（表格文字格式与行距）

- `[table.text]`：单元格文字与行距的独立控制（此前只能全局改正文）：
  `line_spacing`（倍数）、`space_before` / `space_after`、`font.size` / `font.name` /
  `font.color` / `font.bold` / `font.italic`；只写显式配置的键，默认仍继承 `Normal`。
- `[table] header_bold = false`：表头不加粗（默认 `true`）；`[table.text] font.bold`
  显式写了以它为准。合并单元格（`colspan/rowspan`）同样生效。
- 非法配置明确报 `E5001`（`line_spacing` 非正/非数字、`header_bold` 非布尔、
  `[table.text]` 不是表）。
- 新增 `tests/test_table_text.py`（11 项）；Word COM 核对：字号 9pt、行距 12pt/单倍、
  段前后 0、表头不加粗、黑体 eastAsia 均生效。

### 文档（去掉早期版本细节）

- 早期版本说明收敛为一段历史背景：`docs/development-manual.md` 重写为
  「设计说明（历史与架构）」；`dfm.md` / `config.md` / `word.md` / `ir.md` /
  README / HANDOFF / CHANGELOG 不再出现「剪枝版」「完整版」「第二题」等内部阶段用语。
- 发布测试不再约束 README/手册/速查表的具体表述（只保留存在性与打包完整性检查）。

### 新增（输入编码：UTF-8 优先、GB18030 兜底）

- DFM 源文件 / config / 文献库统一用 `src/docgen/encoding.py` 解码：
  **UTF-8（含 BOM）优先，GB18030 兜底**（兼容 Windows 记事本存的 GBK/GB2312）；
  两种都失败时报 `E5001` 并提示「请另存为 UTF-8」。产物 `.docx` 始终 UTF-8。
- 顺带修掉一个崩溃：文献库之前直接 `read_text(encoding="utf-8")`，
  GBK 文件会抛未捕获的 `UnicodeDecodeError`（traceback）；现在走统一解码。
- 中文条目名/作者/文件路径实测可用（TOML 非 ASCII key 需加引号，如 `["张三2024"]`）。
- 新增 `tests/test_encoding.py`（12 项）：UTF-8 / BOM / GBK / GB18030 /
  不可解码、以及 DFM·config·文献库三条输入路径的 GBK 端到端。
- 文档：manual/config 加「输入编码」说明；LIMITATIONS 新增 B18（只兜底
  UTF-8 / GB18030，Big5/Shift-JIS/无 BOM UTF-16 会报错）。

### 新增（文献引用：GB/T 7714 顺序编码制）

- **`[[cite:key1,key2]]`**：行内文献引用 → `[1]` / `[1,2]` / `[1-3]`
  （连续 3 个以上压成区间）；编号按**首次出现顺序**分配，构建期烘焙
  （不依赖 Word 引文功能，WPS/预览也能看到正确编号）。
- **文献库**：独立 TOML（`[key]` 表），支持期刊/专著/会议/学位论文/标准/电子资源；
  用 `docgen build --refs references.toml` 或 `[bibliography] file = "references.toml"`
  （相对输入文件目录）。
- **`[[bibliography]]`**：参考文献表位置；不写时自动追加到文末。标题默认「参考文献」
  （`[bibliography] title` 可改），借 `Heading 1` 样式但**取消自动编号**
  （`w:numPr/w:numId=0`，Word 实测 list string 为空）。
- **校验**：引用不存在的 key → `E5004`；有 `[[cite:]]` 却没配文献库 → `E5001`；
  空 `[[cite:]]` / 重复 `[[bibliography]]` → `E4001`；`check --refs` 同步校验。
- 新增 `src/docgen/bibliography.py` 与 `tests/test_bibliography.py`（19 项）。
- 限制：只做 GB/T 7714 **数字制**子集，不做 BibTeX 完整语法、CSL 多风格引擎、
  Word 原生 `CITATION`/`BIBLIOGRAPHY` 域（见 LIMITATIONS B17）。

### 新增（表格数值列：小数点 / 个位对齐）

- 新增 `[table] decimal_align = [2, 4]`（1 起列号）：指定列的数据行按
  **小数点对齐**、整数行按**个位对齐**；表头与非数字单元格保持原样。
- 实现：Word 的 `w:tab w:val="decimal"` 在**表格单元格**里实测不生效
  （同样段落放正文里正常），改用「right tab + left tab 同一位置」拆分整数/小数。
- 实测踩坑：制表位若恰好落在 Word **默认制表位**（每 720 twips）整数倍上会被
  当成默认左制表位而失效（3600 失败、3540 正常），实现里错开 60 twips。
- Word 实测（宋体 11pt）：小数行小数点 x=486；整数行末位与小数行个位 x=477。
- 限制：只处理纯数字（`12` / `12.34` / `-0.5`）；`N/A`、带单位、科学计数法保持原样；
  有效位数一致属于内容层面，工具不检查。
- 测试：新增 `tests/test_table_decimal.py`（8 项）。
- 文档：[word.md](docs/word.md)「数值列」一节（含实测表与两个 Word 坑）、
  [config.md](docs/config.md) / [cheatsheet.md](docs/cheatsheet.md) /
  [manual.md](docs/manual.md) 补字段。

### 修复（三线表线宽反了 + 辅助线 / 二线表）

- **三线表按标准线宽重排**：之前默认「栏目线 1pt、顶/底 Word 默认细线」，粗细关系
  正好与规范相反。现在默认 **顶线/底线 1.5pt（粗）、栏目线 0.5pt（细）**，
  三者有明确区分（常见学术规范：顶底 1.5pt 或 0.75–1pt，栏目线 0.5–0.75pt）。
  Word 实测 `LineWidth`：顶/底 12、栏目线 4、辅助线 4（1/8 磅单位）。
- 新增 `[table]` 线宽键：`outer_line_size`（顶/底，默认 `1.5pt`）、
  `header_line_size`（栏目线，默认 `0.5pt`）、`aux_line_size`（辅助线，默认同栏目线）；
  `line_size` 保留为**统一线宽**（旧行为，设了它三条线都用它）。
- 新增 **辅助线** `[[aux]]`：写在表格某行任意单元格里，给该行**上方**加一条辅助横线
  （合计 / 小计 / 统计处理结果行常用），标记本身不渲染文字。
- 新增 **二线表**：`[table] header_line = false` 去掉栏目线，只留顶线 + 底线
  （横向阅读逻辑的表格更适用）。
- 测试：`tests/test_table_borders.py` 扩充（23 项）：默认标准线宽、可配线宽、
  `line_size` 统一覆盖、二线表、`[[aux]]` 加线 / 去标记 / 线宽跟随与覆盖。
- 文档：[word.md](docs/word.md) 新增「三线表的标准线宽」一节（含 Word 实测）、
  [config.md](docs/config.md) / [cheatsheet.md](docs/cheatsheet.md) /
  [manual.md](docs/manual.md) 补字段；[dfm.md](docs/dfm.md) 登记 `[[aux]]`。

### 修复（表头孤行：表头不再单独留在页底）

- **表头与首行数据强制同页**：Word 允许在任意两行之间分页，原先「跨页重复表头」
  只保证表头在下一页重复，却挡不住**表头单独留在上一页页底**。
  实测（宋体 11pt / 1.5 倍行距，A4，填充 17 段把表格推到页底）：
  修复前表头在第 1 页、首行数据在第 2 页；修复后两者都在第 2 页。
- 实现：表头行每个单元格段落写 `w:keepNext`（等价 Word「与下段同页」），
  表头行写 `w:trPr/w:cantSplit`（行内不分页），并保留 `w:tblHeader`（跨页重复）；
  `CT_TrPr` 是 sequence，`cantSplit` 排在 `tblHeader` 之前（`insert_child` 保证）。
- 新增 `[table] header_keep_with_body`（默认 `true`）：关掉才会允许表头孤行。
  只有一行的表格不做 keepNext（避免把纯表头表和表后正文绑在一起）。
- 新增 `tests/test_table_header.py`（7 项）：表头行 `cantSplit`/`tblHeader` 顺序、
  表头段落 keepNext、可关闭、单行表不绑定、非法布尔报 `E5001`、合并单元格路径同样生效。
- 文档：[word.md](docs/word.md) 新增「表头不能孤行」一节（含实测对照表）、
  [config.md](docs/config.md) / [cheatsheet.md](docs/cheatsheet.md) /
  [manual.md](docs/manual.md) 补字段与默认行为。

### 新增（生成后自动转 PDF）

- **`docgen build --pdf`**：docx 生成后自动转 PDF（同目录同名 `out.docx → out.pdf`）。
  配套 `--no-pdf`（覆盖 config）与 `--pdf-engine auto|word|libreoffice`。
- **`[pdf]` 配置段**：`enabled`（默认 `false`）、`engine`（默认 `auto`）、
  `timeout`（默认 120 秒）。
- 引擎选择：优先 **Word**（Windows COM，保真最高：分页/字体/域按 Word 计算，
  不需要 pywin32），其次 **LibreOffice**（`soffice`，可用 `DOCGEN_SOFFICE` 指定路径）；
  都没有时明确报 `E5005` 并给出修复建议。
- PDF 转换失败**保留已生成的 docx**；新增退出码 **3**（环境/外部工具错误）。
- LibreOffice 转换使用独立 `UserInstallation` 临时配置，不与运行中的实例抢锁。
- 新增 `src/docgen/pdf.py` 与 `tests/test_pdf.py`（20 项：引擎探测与优先级、
  Word 脚本转义、`[pdf]` 配置校验、`convert()` 行为、CLI 开关与错误码）。
- Word 实测：`--pdf` → `out.pdf`（126 KB / 1 页）；`[pdf] enabled=true` 自动转；
  `--no-pdf` 覆盖；`--pdf-engine libreoffice` 无 `soffice` → `E5005` / 退出码 3。
- 相对路径也安全：传给 Word 前统一 `resolve()` 成绝对路径——
  Word 的 COM 按自己的进程工作目录（常是 `C:\WINDOWS\system32`）解析相对路径，
  `docgen build -o t.docx --pdf` 原本会报「找不到文件」（包内端到端测试踩到）。
- 文档：`cheatsheet.md`（`--pdf`、`[pdf]` 字段表、错误码/退出码）、
  `config.md`（`[pdf]` 段）、`manual.md`（PDF 输出一节）、
  `README.md`（用法示例）、`HANDOFF.md`（模块地图）、
  `LIMITATIONS.md`（B11 改为「依赖外部引擎」）。

### 新增（避头尾：标点不再出现在行首）

- **默认开启中文避头尾（行首行尾禁则）与标点压缩**。实测根因是
  `python-docx` 自带模板的 `docDefaults` 写着 `w:lang w:eastAsia="en-US"`、
  `characterSpacingControl="doNotCompress"`——此时 Word 即使「避头尾」开着，
  `）」` 仍会出现在行首（225 字压力段落里 2 处）。
  引擎现在默认写 `eastAsia="zh-CN"` + `w:kinsoku` / `w:overflowPunct`
  （`true`）+ `compressPunctuation`，同一段文本 **0 处**行首标点。
  实测对照：仅加 `kinsoku`/`overflowPunct` 仍 2 处；再加压缩 1 处；
  语言改 `zh-CN` 后 0 处——**语言标记是决定性因素**。
- 新增 `[document]` 配置键：`east_asia_lang`（默认 `zh-CN`，可换 `zh-TW` / `ja-JP` /
  `ko-KR`）、`kinsoku`、`overflow_punct`、`compress_punctuation`、`auto_space`。
  非法语言标记或布尔值报 `E5001`（不静默取默认）。
- 设置写在 `settings.xml`（按 `CT_Settings` 的 sequence 插入）与
  `styles.xml` 的 `docDefaults`；模板构建路径同样生效。
- 新增 `tests/test_typography.py`（9 项）：默认全开、语言可换、
  各开关可关、`settings` 子元素顺序符合 schema、非法值报错。
- 文档：`word.md` 新增「避头尾」一节（含实测表）、`config.md` / `cheatsheet.md` /
  `manual.md` 补字段与默认效果。

### 新增（表格线可配 + 斜线表头）

- **表格线不再只有三个预设**：新增
  `[table] line_style` / `line_size` / `line_color`（线型/粗细/颜色）、
  `style = "custom"` + `edges = { top = "single", ... }`（逐边）、
  `row_lines = true`（每行底部横线，模拟行分隔线）。
  底层：`CT_TblBorders` / `CT_TcBorders` 的每条边现在都写 `val`/`sz`/`color`，
  之前只写 `val`，线宽颜色只能吃 Word 默认值。
- **斜线表头**：表格单元格里写 `[[diag:右上;左下]]` → `w:tcBorders/tl2br` 斜线 +
  右上右对齐 / 左下左对齐两段文字。分隔符用 `;`（`|` 是 GFM 单元格分隔符，会把表拆坏）。
  顺带修掉一个 schema 顺序隐患：同一单元格先后写 `bottom` 与 `tl2br` 时，
  元素顺序由 `insert_child` 保证（`CT_TcBorders` 是 sequence）。
- 未知 `[table] style` 现在明确报 `E5001`（以前静默退回三线表）。
- 已知边界见 LIMITATIONS B15：行高、按厘米列宽、逐格边框（斜线除外）、DFM 合并语法仍没有。

Word 实测：`line_size = "1pt"` → 线宽 8（1/8 磅）；`edges` 逐边生效；
斜线表头单元格 `DiagonalDown = single`，两段文字对齐正确。

### 新增（速查表与语义手册）

- 新增 [docs/cheatsheet.md](docs/cheatsheet.md)：一页速查——最常用 config、
  字段总表、语法标记、单位、CLI、错误码、不写 config 时的默认效果。
- 新增 [docs/manual.md](docs/manual.md)：语义手册细节版——默认值来源、覆盖层级、
  边界情况、常见任务配方。默认值都是程序化采集的真实值
  （母版 11pt / 1.15 行距 / 标题 14-13-11pt / 三线表等）。
- README / HANDOFF / docs/config.md / docs/dfm.md / docs/word.md / LIMITATIONS 同步：
  补表格线字段、`[[diag:]]` 标记、B15（行高/按厘米列宽/逐格边框/合并语法仍不支持）。
- 测试：文档守卫（速查表覆盖所有配置段与语法标记、README 链接、文档存在）。

### 修复（PowerShell 脚本兼容 5.1）

- **`.ps1` 现在同时支持 Windows PowerShell 5.1 与 PowerShell 7**，不再需要装 pwsh。
  两个实际障碍都修了：

  - **编码**：脚本存成 UTF-8 **带 BOM**。5.1 读无 BOM 的 `.ps1` 会按系统 ANSI 代码页
    解码（中文 Windows 是 936），中文注释/输出变乱码，甚至破坏引号导致语法错。
    本机 ACP 恰好是 65001，所以这个问题只在别人机器上暴露。
  - **tar.gz**：`package.ps1` 现在优先用 `%SystemRoot%\System32\tar.exe`（bsdtar），
    并用 `--version` 校验。此前从 Git Bash/MSYS2 启动时 PATH 里 GNU tar 在前，
    它把 `C:\...` 当远程主机名（`Cannot connect to C: resolve failed`），tar.gz 静默失败；
    而 5.1 没有 .NET `TarFile` 兜底，结果只出 zip。
  - 两个脚本都加了 `#Requires -Version 5.1`，用法示例里补了
    `powershell -File scripts\setup.ps1 --dev`。

- 新增 [scripts/README.md](scripts/README.md)：四个安装入口、两个 PowerShell 版本的
  支持矩阵，以及 BOM / tar 这两处差异的原因。
- 新增测试：`.ps1` 必须有 UTF-8 BOM、必须声明最低版本、`package.ps1` 必须优先用
  System32 bsdtar；`.cmd` 仍必须纯 ASCII（不能带 BOM）。

实测：PS 5.1 下 `package.ps1` 能出 tar.gz（135 条目）+ zip，`setup.ps1 --dev` 装好依赖、
未知参数干净退出 2；pwsh 7 下同样通过。

### 新增（段落间距可配置）

- **`space_before` / `space_after`**：`[document]` / `[styles.*]`（body、headingN、
  caption）/ `[image]` 都支持，`[table]` 也有同名键。
  支持两种单位：`"6pt"` / `"12px"` / `"0.2cm"` / 裸数字（按磅）→ `w:before` / `w:after`；
  `"0.5 line"` / `"1行"` → `w:beforeLines` / `w:afterLines`（百分之一行）。
  写错单位**报** `E5001`，不再「写了不生效」。
- **表格与正文不再紧贴**：Word 的表格没有「表格后间距」属性，`[table] space_after`
  会写到**表格后第一段**的段前距、`space_before` 写到**表格前一段**的段后距。
  这样「表格底线贴正文」用一行 config 就能解决。
- 标题只吃「对齐 + 段距」，不会误继承正文的行距与首行缩进；行内样式
  （`[文字]{.样式名}`）也能承载这四个段落级键。

### 修复（图片与图题必须同页）

- **图片与图题可能被分页拆开**：学术排版里「图在上一页、题注在下一页」是硬伤，
  但原先只有标题设了 `keepNext`，图片段落什么都没设。
  现在图片后面紧跟图题时，图片段落自动带 `w:keepNext`、图题段落带 `w:keepLines`，
  图放不下时会**整体**移到下一页。只在后面确实是图题时才加，避免把正文一起拖走。
- **图题默认居中**：模板的 `Caption` 样式预置 `w:jc=center`（规范要求图题在图片
  正下方居中）；`[styles.caption] alignment` 可覆盖，`first_line_chars` 也能用了。
- 实测（Word 读真实页码）：去掉 `keepNext` 时图片在第 1 页、题注在第 2 页；
  加上之后两者一起落到第 2 页。
- 已知边界（[LIMITATIONS.md](LIMITATIONS.md) B14）：表格题注无法强制与表格同页
  （Word 表格不支持 `keepNext`）；图元注/整图注没有独立入口。

### 修复（试用人反馈：域缓存值）

- **`SEQ` / `REF` 域的缓存结果全部写死 `"1"`**：Word 打开时会按 `updateFields` 重算，
  所以 Word 里看不出来；但 WPS / Office 预览 / 网页版 / 解包 XML 的脚本只读缓存值，
  于是整篇图号都显示「图 1」、引用全是「1」。
  现在渲染期先算好编号写进缓存：

  - `SEQ 图/表/公式` → 该类型内的真实序号（按文档顺序，前向引用也正确）；
  - `REF 目标` → 目标题注序号；编号公式是 `(N)`（书签包住的就是括号形式）；
  - 算不出来的引用留**空**，不再写死 `1`（空不会撒谎，Word 仍会重算）；
  - `PAGE` / `TOC` 仍由查看器更新（分页相关，渲染期无法计算），见 LIMITATIONS B13。

- **`w:updateFields` 位置不合 schema**：原先 `append` 到 `settings.xml` 末尾。
  `CT_Settings` 的元素顺序是固定的，严格实现会忽略它——那样连 Word 都不会自动更新域。
  现在按官方 XSD 的 `CT_Settings` 顺序插入（96 个元素的位置表进了 `CHILD_ORDER`），
  并有测试断言整份 settings 的子元素顺序单调（防止以后再加 settings 元素时踩回去）。

实测验收（同一份最小复现，按「不更新域」方式读文本）：

```text
修复前: 图 1 / 图 1 / 图 1，引用 1 / 1 / 1
修复后: 图 1 / 图 2 / 图 3，引用 1 / 2 / 3
```

Word 16 复核：打开显示 1/2/3，`Fields.Update()` 后仍为 1/2/3，无修复提示。

### 修复（试用人反馈的 6 条，逐条用 Word COM 实证）

- **① `[styles.caption]` 完全不起作用**：题注段落用内置 `Caption` 样式，config 的
  字体/字号/颜色没人写进去。
  现在它们写进 `Caption` 样式（与 `[styles.body]` → `Normal` 同一套机制）；
  同时把母版自带的「加粗 + 主题蓝 4F81BD + 9pt」**中性化**——没声明就不该自带强调色。
  Word 复核：题注 `Color=C00000`、`Size=10.5`、非加粗 ✅
- **② 标题 `font.name` 缺 `w:eastAsia`**：Word 对中文字符取 `eastAsia`，只写
  ascii/hAnsi/cs 时 `font.name = "黑体"` 对中文是**空操作**。
  现在 run 级会写 `eastAsia`；代码块/行内代码除外（等宽字体无中文字形，留给样式链）。
- **③ `alignment` 从未生效**：`docs/config.md` 早把它列为段落键，产物里却
  **一处 `w:jc` 都没有**。现在 `[document] alignment` 作默认，
  `[styles.body]` / `[styles.headingN]` 覆盖；标题也能居中。
  支持 `left/right/center/justify(=both)`，非法值退回左对齐（纯外观，不中断构建）。
- **④ Heading 样式定义仍是主题蓝**：只写 run 级时，Word 样式面板与「新敲一个标题」
  仍回主题色。现在 `[styles.headingN]` 的字体/字号/颜色/加粗同时写进**样式定义**，
  并清掉 `themeColor` / `*Theme` 主题属性（它们优先级高于显式值）。
- **⑤ 有序列表跨小节连续编号**：所有列表段落只挂 `List Number` 样式，
  编号来自样式自带的单个 `numId` → 全文共用计数器（第二个列表显示 3.、4.）。
  现在每个有序列表分配独立 `w:num`，且带 `lvlOverride/startOverride`——
  实测**只换 numId 不够**，Word 对共用 `abstractNum` 的多个实例默认接着数。
  嵌套有序列表同样各自计数。Word 复核：第二段列表回到 1.、2. ✅
- **⑥ `cover = true` 配多节时封面是空页**：分节原先在渲染前一次性建好，
  内容只能落进最后一节。
  新增 `[[sectionbreak]]` 标记（`SectionBreak` IR 节点）让内容能分到前面的节：
  写封面内容 → `[[sectionbreak]]` → 正文。不写标记时仍是旧行为，
  但文档里明确说明 `cover = true` 只做垂直居中、不会凭空产生内容。
  Word 复核：封面节含标题/署名、`vAlign=center`、`UpperRoman`；
  正文节 `top`、`Arabic` 从 1、有页眉页脚 ✅

### 移除

- **移除 HTML 后端**（`render/html.py` + `render/css.py`，共 449 行）。
  它原本是 Word 后端的**参照实现**（「HTML 对了 Word 不对 → 问题在渲染层」），
  但维护成本高于收益、需求很少，且它的测试面（28 项）比实际使用价值更大。
  随之移除的还有 `test_html_probe.py`（28 项）与特性矩阵里的 HTML 用例。
  - `docgen build --format html` 现在**明确报错**（不再静默产出 docx）；
    默认输出改为 `output.docx`。
  - **config 只认点号键**：`font_weight` / `font_size` / `color` 这类扁平键
    不再有任何后端读取（写它们不报错、也不生效），见 [LIMITATIONS.md](LIMITATIONS.md) A5。
  - 「config 是唯一真源」这条不变量**没有丢**：改由新的
    [tests/test_config_source_of_truth.py](tests/test_config_source_of_truth.py) 在
    **docx 侧**守（config 里声明的每个样式值都必须真的到达产出，且行内语义样式
    必须落在正文 run 上，不能只躺在 styles.xml 里）。

### 修复

- **嵌套表里的 `@ref` 从不解析**：`[styles.body] font.size = "@document.font.size"`
  这种写法解析不到（解析器只作用于顶层字符串值），字符串一路带到渲染层，
  在单位换算里炸掉（`could not convert string to float`）。
  `examples/minimal/config.toml` 正是这么写的。现在递归解析嵌套表。
- **`[styles.body]` 的字体类属性不生效**：正文段落只被应用段落级的
  `line_spacing` / `first_line_chars`，`font.color` / `font.name` / `font.size`
  这些字符级属性没人读——「config 写了但不生效」这类最隐蔽的失效方式。
  现在它们会写进 `Normal` 样式（正文继承它）。

### 测试版发布准备（0.1.0b1）

- **工作区整理**：清掉缓存/构建产物（193MB → 19MB）；`.github/workflows/ci.yml` 此前
  **从未提交**，现已纳入仓库；临时草稿 `.tmp/` 删除，其中唯一一份《开发手册》
  转正为 [docs/development-manual.md](docs/development-manual.md)
  （源码与 README 里大量「手册 §N」引用它，不能再放临时目录）
- **CI 首次本地复刻**：修掉两处会让 CI 必红的问题——`ruff format --check .` 会重排
  `docs/development-manual.md` 里的**契约代码**（现已排除该文件）
- **版本单一真源**：新增 `docgen.version_string()`，优先读已安装包元数据
  （`pyproject.toml` 是唯一真源），模块常量仅作未安装时的兜底，一致性由测试守住
- **新增发布物**：[scripts/package.sh](scripts/package.sh) 打源码测试版（tar.gz / zip），
  另有 PowerShell / cmd 等价入口（`package.ps1` / `package.cmd`）
- **新增文档**：[QUICKSTART.md](QUICKSTART.md) 上手、
  [LIMITATIONS.md](LIMITATIONS.md) 已知限制清单（含「看着像 bug 其实不是」）、
  [FEEDBACK.md](FEEDBACK.md) 反馈模板
- **同步一律 `--frozen`**：不带它的话，**换个软件源同步就会把 `uv.lock` 里
  500+ 处 URL 改写成那个源**（实测踩到）。`--frozen` 仍然按 `--index` 去镜像下载，
  只是不改锁文件。已加测试守住（每条同步命令都要带 `--frozen`，bash 与 pwsh 版都查）
- **网络来源不再写死**：内外网状态会随时间变化（现实因素），所以新增
  [scripts/setup.sh](scripts/setup.sh)（另有 `setup.ps1` / `setup.cmd` 两个等价入口）
  ——依次尝试「镜像直连 → PyPI 直连 → 代理 + PyPI →
  代理 + 镜像」，**用真实同步判断可用性**，哪个成功用哪个，并支持 `--index` / `--proxy`
  手动指定。文档里不再出现「直连一定超时」这类会过期的断言
  （本机实测：直连 PyPI 与 files.pythonhosted.org 超时、代理下 pypi.org 通但
  files.pythonhosted.org 仍不通、镜像直连通——但这些都可能变）
  - 注：第一版脚本用「先探测再同步」两段式，结果探测本身依赖环境而**假失败**
    （`uv pip install --dry-run` 需要已存在的 venv），已改为直接同步 + 短超时换源
- **脚本三平台入口**：`setup` / `package` 各有 `.sh`（Git Bash/macOS/Linux）、
  `.ps1`（PowerShell）、`.cmd`（cmd）三个入口，做同一件事、参数写法一致。
  `.cmd` 限定纯 ASCII——cmd.exe 按控制台代码页读文件，中文注释会被读成乱码
  甚至当命令执行（实测踩到）。测试逐个变体检查关键约束，防"改了 bash 忘了 pwsh"

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

### 新增（分节 / 页码 / 页眉页脚 / 封面）

- **分节**：`[[sections]]` 配置纸张（A4/A3/A5/Letter/Legal）、页边距（cm）、分节符
- **页码体系**：`numbering.format`（decimal / upperRoman / lowerRoman / upperLetter）
  与 `numbering.start`（重启）→ `w:pgNumType`；页脚里的 `PAGE` 变成页码域
- **页眉页脚**：每节独立（`is_linked_to_previous = False`），避免 Word 继承错乱（§17.1）
- **封面**：`cover = true` → `sectPr` 的 `w:vAlign val="center"` 垂直居中

### 新增（表格 / 图片 / 脚注）

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

### 新增（编号 / 题注 / 交叉引用）

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

### 新增（数学渲染）

- **数学引擎**：`render/math.py` 把 LaTeX 经 `latex2mathml` → MathML → Office
  `MML2OMML.XSL` → **OMML**（`m:oMath`），公式在 Word 里可编辑
- `[math]` 配置：`engine = auto|xsl|plain`、`on_fail = plain|error`（`E5002`）、`xsl` 路径；
  也可用环境变量 `DOCGEN_MML2OMML`；找不到 XSL 时自动降级，构建不会挂
- 行内与块级公式共用引擎；块级公式居中且不带首行缩进
- 公式测试集 40 条，转换通率 **40/40 = 100%**（手册验收 > 90%）
- 修复确定性测试：比 `document.xml` 而不是 docx 字节（zip 时间戳不可比）

### 新增（基础渲染 + 母版槽位）

- **上下标**（手册 §6.2.3）：`H~2~O` / `E=mc^2^`（Pandoc 单字符标记）与
  `[上标]{.sup}` / `[下标]{.sub}`，Word 侧写 `w:vertAlign`
- **母版构建**：`render/template_build.py` 幂等补齐 §14.1 槽位——`TOC 1..9` 样式、
  多级标题编号（`numId=100`，`Heading1`→`1`、`Heading2`→`1.1`）、
  `HeadingN` 的 `outlineLvl` 与 `numPr` 绑定、`updateFields`；
  `tests/test_template.py` 断言全部槽位（CI 重建即验证）
- 文档：`docs/word.md` 补母版与已实现清单；`docs/dfm.md` 补上下标语法

### 新增（最小 docx 链路）

- **Word 后端**：`docgen build -o out.docx` 与 `--format=docx` 端到端可用
- [render/ooxml.py](src/docgen/render/ooxml.py)：所有 `OxmlElement` 构造集中一处，
  处理手册 §17.1 的陷阱（四个 `rFonts`、`firstLineChars`、`beforeLines`/`afterLines`、
  `outlineLvl`、`updateFields`）
- [render/template.py](src/docgen/render/template.py)：母版加载、样式槽位校验、
  标题 `outlineLvl`、`updateFields`
- [units.py](src/docgen/units.py)：`12pt` / `16px` / `1.5em` / 纯数字 → 磅
- **config 点号键**：`[document] font.name = "宋体"`、`[styles.x] font.bold = true`
  （手册 §6.1 口径），展开后为嵌套表
- **错误码扩展**：`E2010` keywords 非法、`E3002` `\begin` 名字不一致、
  `E5002` 数学转换失败、`E5003` 分节配置、`E5004` 编号/引用不存在
- **OOXML 语义探针**：`tests/test_ooxml_probe.py`（样式槽位、`outlineLvl`、
  四个字体属性、`firstLineChars`、`updateFields`、分页符、表格边框、
  config 值 == 输出属性的不变量、确定性、图片嵌入）
- 文档：[docs/word.md](docs/word.md)

### 计划中

## [0.1.0] - 2026-10-10

首个可交付版本：`DFM + TOML → HTML` 全链路可用（那时只有 HTML 后端，Word 后端随后加入）。
当时的测试条数与覆盖率以当时的提交为准；当前值见 `main` 的 tip。

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

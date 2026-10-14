# Word（docx）后端

完整版（Hard Version）在剪枝版地基上新增的渲染后端。**IR 与 config 都不变**：
同一份 IR，HTML 渲染器是参照，Word 只是第二个消费方（手册 §2.3）。

## 用法

```bash
# 按输出扩展名自动选择后端
docgen build input.md -c config.toml -o output.docx

# 显式指定格式
docgen build input.md -c config.toml -o output.docx --format docx
docgen build input.md -c config.toml -o output.html --format html
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
| 交叉引用 | `[[ref:fig:1]]` → `REF fig:1 \h` 域（域结果即题注编号，`\h` 带超链接）；HTML 侧是 `#fig:1` 锚链接 |
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
脚注（`[[fn:文字]]` → 手写 `word/footnotes.xml`）。

**W5 已实现**：分节（`[[sections]]` → 纸张/页边距/分节符）、页码体系
（`w:pgNumType` 格式 + 重启 + 页脚 `PAGE` 域）、页眉页脚（每节独立、`is_linked_to_previous=False`）、
封面（`sectPr` 的 `w:vAlign` 垂直居中）。

**后续阶段**：`docgen init --preset` 预设库、视觉回归（LibreOffice headless）、
打包发布、公式图片降级（matplotlib）、`docgen format`。

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

| 能力 | 实现 |
|---|---|
| 分节 | 第 1 条配置作用于已有节，其余 `add_section(nextPage)` |
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
- **不做全文 `document.xml` 快照**（手册 §10.1：属性顺序与库版本差异会让它脆弱）。

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

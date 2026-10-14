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
`[[toc]]`（TOC 域）、编号映射显式化、`E5004`/`E4001` 校验。

**后续阶段**：表格合并/固定列宽/重复表头、脚注（`footnotes.xml`）、图片尺寸与对齐、
分节/页眉页脚/页码、封面、`docgen init --preset`、公式编号（无边框三列表格）、公式图片降级。

## 测试

- [tests/test_ooxml_probe.py](../tests/test_ooxml_probe.py)：OOXML 语义探针
  （样式槽位、`outlineLvl`、四个字体属性、`firstLineChars`、`updateFields`、
  分页符、表格边框、`config 值 == 输出属性` 不变量、确定性输出、图片嵌入）。
- **不做全文 `document.xml` 快照**（手册 §10.1：属性顺序与库版本差异会让它脆弱）。

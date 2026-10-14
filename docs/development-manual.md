# DocGen 完整版（Hard Version）开发手册

> 版本：v1.0  
> 目标：在剪枝版基础上，实现完整的 Word 排版编译器  
> 定位：第二题，正式 Word 渲染后端  
> 周期：12~19 周（单人 + AI 辅助）  
> 前置：剪枝版已完成（DFM → IR → HTML 跑通）  
> 本文档为交接与开发基线，所有决策以本文档为准

---

## 目录

0. 文档信息  
1. 项目定位与目标  
2. 与剪枝版的关系  
3. 前置条件与检查清单  
4. 技术栈新增  
5. 架构与数据流  
6. 三份契约  
7. 模块设计  
8. 目录结构  
9. 开发阶段与周计划  
10. 测试策略  
11. CLI 扩展  
12. 错误码扩展  
13. 验收标准  
14. 母版要求  
15. 风险与对策  
16. 明确不做  
17. 附录：OOXML 陷阱、学习资源、术语表

---

## 0. 文档信息

- **项目名**：DocGen 完整版（Hard Version）
- **版本**：v1.0
- **周期**：12~19 周（单人 + AI 辅助）
- **产出**：可用的 `docgen` CLI，支持 DFM + TOML → Word (.docx)
- **核心原则**：解析 / IR / 渲染分离；config 驱动；可测试不变量；确定性输出
- **前置**：剪枝版已完成，IR 稳定，HTML 渲染器可作参照
- **后续**：可扩展 PDF、LaTeX、docx 导入器等

---

## 1. 项目定位与目标

**DocGen 完整版是一个 config 驱动的纯文本 → Word 排版编译器。**  
输入：DFM 内容 + TOML 配置。  
输出：符合机构排版规范的 Word 文档。

**服务对象**：算法竞赛/技术报告场景下，有算法竞赛背景、愿意用文本写内容、借助 LLM 生成与改写的用户。

**核心痛点**：用户在写报告时手改格式的繁琐操作。不是“没有排版工具”，是“已有内容但每次都要手动调格式”。

**心智模型**：输入是源码、输出是目标码、中间有 IR、config 是符号表、错误有行号、输出确定性、行为可测试。

### 1.1 目标

- 在剪枝版基础上，新增 Word 渲染后端
- 支持完整的 DFM 方言（含 `\begin{...}` 命名块）
- 支持完整的 config 系统（继承、`@ref`、include、内联覆盖）
- 实现 Word 专有功能：编号、题注、交叉引用、脚注、表格合并、数学、代码块高亮、分节、页眉页脚、目录
- 建立 OOXML 探针测试、视觉回归测试
- 产出可分发工具，带预设库

### 1.2 非目标（完整版仍不做）

- PDF 渲染器（视觉回归走 LibreOffice headless）
- 所见即所得 / GUI / 实时预览
- 参考文献 BibTeX/CSL（Phase 3 后按反馈评估）
- 插件系统
- 支持所有语言（只做冻结清单）
- 语言检测、自动识别伪代码
- 语法解析（只做词法高亮）
- 深合并、多继承、条件继承、动态继承
- 跨命名空间继承
- 运行时合并
- 全文 `document.xml` 快照
- 图形化配置编辑器
- 服务化 / 不可信输入处理（除非未来决定）

**每加一条“也许用户想要”，先问：它冲掉哪条现有约束？**

---

## 2. 与剪枝版的关系

### 2.1 剪枝版留下的资产

| 资产 | 状态 | 完整版如何使用 |
|---|---|---|
| DFM 解析器 | 完成 | 直接复用，仅扩展 `\begin` 规则 |
| IR 定义 | 完成 | 直接复用，仅扩展节点（Footnote、Field、SectionProperties 等） |
| config 系统 | 完成 | 直接复用，仅扩展 Word 相关字段 |
| 错误码体系 | 完成 | 直接复用，新增 Word 相关码 |
| CLI 骨架 | 完成 | 扩展 `--format=docx` |
| 测试基础设施 | 完成 | 直接复用，新增 OOXML 探针 |
| normalize / canonicalize | 完成 | 直接复用 |
| HTML 渲染器 | 完成 | 作为参照实现，对照调试 |

### 2.2 剪枝版未做的、完整版要做的

- `\begin{...}\end{...}` 命名块
- Word 渲染后端（`render/docx.py`、`ooxml.py`）
- 母版处理
- 数学渲染（MathML → OMML）
- 编号 / 题注 / 交叉引用 / 目录 / 域
- 脚注 / 尾注
- 表格合并、固定列宽、重复表头、斜线表头（可选）
- 分节 / 页码 / 页眉页脚
- 封面 / 预设库

### 2.3 过渡策略

1. **不碰剪枝版已有模块**：DFM、IR、config、CLI、测试基础设施保持稳定。
2. **新增 Word 渲染层**：所有 Word 相关代码放在 `render/docx.py` 和 `ooxml.py`。
3. **IR 只做向后兼容的扩展**：新增节点字段可选，不破坏已有节点。
4. **HTML 渲染器作为参照**：同一份 IR，HTML 对了 Word 不对，问题在渲染层。

---

## 3. 前置条件与检查清单

在开始完整版前，确认剪枝版已完成：

- [ ] `docgen build` 能生成 HTML
- [ ] config 继承、`@ref`、`include` 全部测试通过
- [ ] DFM 子集全部节点能解析成 IR
- [ ] HTML 输出样式与 config 一致
- [ ] `docgen check --json` 可用
- [ ] 退出码正确
- [ ] 测试覆盖率 > 70%
- [ ] ruff / mypy / CI 全绿
- [ ] 文档齐全：DFM、config、IR、README
- [ ] 3 个示例可运行
- [ ] IR 定义稳定，frozen dataclass
- [ ] 临时 Word 输出（如果有）已删除或标记为废弃

---

## 4. 技术栈新增

| 用途 | 选型 | 说明 |
|---|---|---|
| Word 操作 | `python-docx >= 1.1` | 核心库 |
| OOXML 操作 | `lxml >= 5.0` | XPath、命名空间、OxmlElement |
| 数学转换 | `latex2mathml >= 3.0` + MML2OMML.XSL | 纯 Python，公式可编辑 |
| 数学兜底 | 图片降级（matplotlib） | 转换失败时保证视觉正确 |
| 数学可选后端 | `pandoc`（不进核心路径） | align/矩阵/分段函数质量更高 |
| 母版 | Word `.dotx`（解包 XML 入库） | 多级编号、TOC1-9、eastAsia 字体 |
| 视觉回归 | LibreOffice headless → PDF → 栅格 diff | CI 近似验证 |
| 字体 | 中文字体（思源、宋体替代） | CI 环境需安装 |

**包版本基线**：

- `python-docx >= 1.1`
- `markdown-it-py >= 3.0`（已有）
- `latex2mathml >= 3.0`
- `lxml >= 5.0`
- Python `>= 3.11`

---

## 5. 架构与数据流

```
config.toml ─┐
             ├─► config 解析 ─► 符号表（样式表，最终值）
content.txt ─┘                        │
                                      ▼
       DFM 解析（markdown-it-py + 自定义规则）─► raw IR
                                      │
                                      ▼
                   语义校验（样式/编号/引用）─► valid IR
                                      │
                                      ├─► HTML 渲染器（已有，参照）
                                      │
                                      ▼
                         Word 渲染层（python-docx + OOXML 片段）
                                      │
                                      ▼
                               output.docx
```

**三条铁律（完整版同样适用）：**

1. **解析 / IR / 渲染彻底分离**：渲染层只认 IR，不认原始标记。IR 是输入源无关的。
2. **唯一真源 = config**：母版只提供“结构与槽位”，一切格式值由引擎从 config 无条件写入。合并、继承、`@ref` 全部在解析期完成，渲染期只有终值。
3. **可测试不变量**：输出中每个样式属性 == config 声明值。写成测试，让“config 驱动”从口号变断言。

---

## 6. 三份契约

### 6.1 config（TOML）

#### 6.1.1 顶层结构

```toml
config_version = "0.3"
include = ["base.toml", "presets/oi-report.toml"]

[page]
size = "A4"
margin.top = 2.54

[document]
font.name = "宋体"
line_spacing = 1.5

[header]
footer = ...

[styles.heading1]
...

[styles.body]
...

[code_block.python]
...

[cover]
...

[[cover_items]]
...

[table]
...

[math]
...

[image]
...

[[sections]]
...
```

**禁止**：config 里出现“有序 run 序列”结构（出现即抽象层错了）。

#### 6.1.2 include 机制

- `include = ["a.toml", "b.toml"]` 按顺序合并，后者覆盖前者（深度优先）。
- 带 `preset_version`、`word_version`、校验和。
- 每个被 include 的文件自带 `config_version`，主文件版本必须 ≥ 所有 include。

#### 6.1.3 样式继承（L2 单继承）

```toml
[styles.keyword]
font.name = "Consolas"
font.bold = true
font.color = "0000FF"

[styles.keyword_return]
based_on = "keyword"
font.color = "FF0000"       # 浅合并：字段级覆盖
```

**四条冻结规则**：

1. **浅合并，字段级覆盖**。子表整表替换，不递归。
2. **链式继承，深度上限 8**。
3. **循环检测**，报错指出环路径。
4. **解析期展开**，输出终值。渲染器拿到的都是最终值。

**`@ref` 引用**：`font = "@mono"` 在取值时替换。

**取消字段**：`for = false` 表示禁用该词高亮（软删除，可被后续继承恢复）。

#### 6.1.4 引用处局部覆盖

- 只在**叶子引用点**允许内联覆盖：`return = {based_on = "@keyword", font.color = "FF0000"}`
- **不允许**内联写 `based_on`（避免隐形子类）
- **最多 1 层**，不允许内联表再引用内联表
- 字段名必须在已知字段集内，拼错报错
- **禁止**：`@keyword[color=X]` 迷你语法、运行时修改

#### 6.1.5 伪代码关键字配置

```toml
[code_block.algorithm]
based_on = "code_block.text"
line_numbers = true
keywords_mode = "loose"

[code_block.algorithm.keywords]
for     = "@keyword_control"
while   = "@keyword_control"
return  = "@keyword_return"
input   = "@keyword_io"

[code_block.algorithm.types]
int    = { italic = true, color = "008000" }
```

#### 6.1.6 关键规则汇总

| 规则 | 值 |
|---|---|
| 继承深度上限 | 8 |
| 合并语义 | 浅合并，字段级覆盖 |
| `@ref` 解析时机 | 解析期 |
| 内联覆盖层数 | 最多 1 层 |
| `false` 语义 | 软删除 |
| 跨命名空间继承 | 不允许 |
| 多继承 | 不允许 |

### 6.2 DFM（DocGen Flavored Markdown）

#### 6.2.1 定位

**放弃“兼容 Markdown”**。定义为 DFM，明确支持/禁用/扩展。规则冻结后不随上游 Markdown 演进。

#### 6.2.2 块级（沿用 Markdown）

```
# ## ###         标题
- * +            无序列表
1. 2.            有序列表
>                引用
```lang ... ```   代码块
---              分隔线
|a|b|            表格（GFM 风格）
```

**唯一硬规则**：缩进统一 4 空格。

#### 6.2.3 行内（Pandoc 属性语法）

```
**粗体** *斜体* ~~删除~~ `code`
[红色文字]{color=red}
[引用样式]{.caption}
[上标]{.sup}
H~2~O  E=mc^2^
```

**为什么不用自研 `[[b]]`**：LLM 对 `[text]{.style}` 的生成质量远高于对 `[[custom]]` 的生成质量。

#### 6.2.4 数学

- 行内 `$x^2$`，块级 `$$ ... $$`
- 规则按 Pandoc 定义：`$` 前后非空白才构成定界符
- 转义 `\$` 表字面美元
- **代码块和行内代码内不解析数学**（硬规则）
- **数学内不解析 Markdown**（硬规则）
- `\begin{...}` 在数学环境内**不识别**，作为数学内容

#### 6.2.5 双语法：fence 与 `\begin`

**问题**：CommonMark 的 fence 长度规则对 LLM 不友好。

**解法**：双语法并存。

##### 代码块

简单场景：
````markdown
```python
print("hi")
```
````

嵌套 / 含终止符场景：
```latex
\begin{code:python}
print("hi")
\end{code:python}
```

**规则**：
- 开标签 `\begin{code:语言名}`
- 闭标签 `\end{code:语言名}`
- **首尾语言名必须一致**，不一致报错 E3002
- 内部内容**原样保留**，不解析任何 DFM 标记
- 嵌套时只需名字配对

##### 命名块（替代 fenced div）

```latex
\begin{caption}
图 1 系统架构
\end{caption}

\begin{equation #eq:main}
$$ E = mc^2 $$
\end{equation}

\begin{abstract}
本文提出……
\end{abstract}
```

**规则**：
- `\begin{名字}` 或 `\begin{名字 属性}`
- 闭标签 `\end{名字}`
- 名字必须一致
- 属性沿用 Pandoc 属性语法（`{.caption #fig1}`）

##### 双语法切换规则

| 场景 | 推荐语法 | 理由 |
|---|---|---|
| 简单代码块，内部无 ``` | ` ```lang ` | 简洁，LLM 熟 |
| 代码块内部含 ``` | `\begin{code:lang}` | fence 会提前终止 |
| 代码块嵌套 | `\begin{code:lang}` | 长度规则 LLM 不可靠 |
| fenced div（题注/公式/容器） | `\begin{名字}` | 嵌套安全 |
| 行内标记 | 不变（`[...]{...}`） | 无嵌套问题 |

**核心原则**：凡是需要“嵌套同类结构”或“内部含终止符”的场景，一律用 `\begin...\end`。

##### 冲突处理

- `\begin{...}` **必须独占一行**（可含前后空白）
- 行内出现 `\begin` 作为普通文本，不识别
- 需要字面量时用 `\\begin` 或 `\verb`
- `::: {...}` 的 fenced div 语法**保留**，但文档推荐嵌套时用 `\begin`

#### 6.2.6 自研标记白名单

只有五条：

```
[[img:path]]      行内图片
[[toc]]           目录占位
[[pagebreak]]     分页
[[ref:fig1]]      交叉引用
\begin{...}...\end{...}     命名块（代码 / div 通用）
```

#### 6.2.7 四条冲突规则（冻结）

1. **代码优先级最高**：` ``` ` 块、`\begin{code}` 块和 `` ` `` 内不解析任何标记
2. **数学次之**：`$...$` 内不解析 Markdown
3. **属性语法第三**：`[...]{...}` 内不解析嵌套 `[...]`
4. **转义兜底**：`\` 转义后面一个字符

### 6.3 IR

#### 6.3.1 节点定义（完整版）

```python
@dataclass(frozen=True)
class BlockNode:
    source_line: int

Heading(level, inline_content, source_line)
Paragraph(inline_content, source_line)
List(ordered, items: list[ListItem], source_line)
Table(cells: list[list[TableCell]], source_line)
Formula(latex, display: bool, number: str|None, source_line)
Image(src, alt, width, align, source_line)
Caption(target, text, source_line)
Toc(source_line)
PageBreak(source_line)
Footnote(content: list[BlockNode], source_line)
SectionProperties(config: dict, source_line)
Field(kind, args, source_line)
CodeBlock(language, content, source_line)
NamedBlock(name, attributes, content: list[BlockNode], source_line)

@dataclass(frozen=True)
class InlineNode:
    pass

Text(content)
Styled(content, style_name)
Math(latex, display)
Image(src, alt)
Break()
Ref(target)
Hyperlink(url, content)
Bookmark(name)
```

#### 6.3.2 TableCell

```python
@dataclass(frozen=True)
class TableCell:
    blocks: list[BlockNode]           # 段落 / 列表 / 公式 / 图片
    colspan: int = 1
    rowspan: int = 1
    is_merge_continuation: bool = False
    diag: int = 0                     # 斜线表头：0/1/2/3
    diag_parts: list[str] = field(default_factory=list)
```

**两条硬约束**：
- cell 内**禁止嵌套表格**
- cell 内 block 序列**最多 2 层**

#### 6.3.3 通用规则

- 所有节点：带 `source_line`（报错指向 content.txt 第 N 行）
- 所有节点：**frozen dataclass**
- 所有节点：字段名与 Markdown 无关
- **v1 必须存在的节点**：Caption、Footnote、Field（TOC/SEQ/STYLEREF/REF/PAGE 统一容器）
- **延后**：SectionBreak（由 config 的 `[[sections]]` 描述，渲染时才生成 sectPr）、Hyperlink/Bookmark（Markdown 自然出现，渲染时直出）

#### 6.3.4 IR 是输入源无关的

任何未来新增的输入源（docx 导入器、其他标记语言）都必须产出与 DFM 解析器相同形状的 IR，不需要改动渲染层。

---

## 7. 模块设计

| 模块 | 职责 | 关键文件 |
|---|---|---|
| CLI | 命令行入口 | `cli.py` |
| 错误码 | 统一错误定义与格式化 | `errors.py` |
| 输入规范化 | UTF-8、LF、去 BOM | `normalize.py` |
| 输出规范化 | 确定性输出 | `canonicalize.py` |
| config 解析 | TOML + 继承 + @ref + include | `config.py` |
| IR 定义 | frozen dataclass | `ir.py` |
| DFM 解析 | markdown-it-py + 自定义规则 → IR | `parser/dfm.py` |
| 语义校验 | 样式引用、编号、引用、图片路径 | `validate.py` |
| HTML 渲染 | IR → HTML（参照） | `render/html.py` |
| Word 渲染 | IR → docx | `render/docx.py` |
| OOXML 片段 | 所有 OxmlElement 构造 | `ooxml.py` |
| 母版处理 | 解包、版本、样式覆盖 | `template.py` |
| 数学渲染 | LaTeX → OMML | `math.py` |
| 编号 / 题注 | SEQ / STYLEREF / REF 域 | `numbering.py` |
| 分节 / 页眉页脚 | sectPr、页眉页脚继承 | `sections.py` |
| 目录 | TOC 域、updateFields | `toc.py` |

---

## 8. 目录结构

```
docgen/
  pyproject.toml
  README.md
  .github/workflows/ci.yml
  src/docgen/
    __init__.py
    cli.py
    errors.py
    normalize.py
    canonicalize.py
    config.py
    ir.py
    validate.py
    parser/
      __init__.py
      dfm.py
      rules.py
      begin_block.py
    render/
      __init__.py
      html.py
      css.py
      docx.py
      ooxml.py
      template.py
      math.py
      numbering.py
      sections.py
      toc.py
    templates/
      default/
        word/
          document.xml
          styles.xml
          numbering.xml
          settings.xml
          ...
        template.toml
  tests/
    conftest.py
    fixtures/
      minimal.md
      minimal.toml
      inherit.toml
      golden/
        report1/
        report2/
        paper1/
    test_ir_snapshot.py
    test_config_inheritance.py
    test_html_probe.py
    test_ooxml_probe.py
    test_math.py
    test_cli.py
  docs/
    dfm.md
    config.md
    ir.md
    template.md
    ooxml.md
```

---

## 9. 开发阶段与周计划（12~19 周）

### W0：母版选型 + OOXML 入门 + 最小 docx（1~2 周）

**目标**：跑通 `docgen build --format=docx` 生成最简单 docx。

- 选一套真实 `.dotx`，解包入库，打 `template_version`
- 写 `template.py`：加载母版、校验版本、提供样式槽位
- 写 `ooxml.py` 骨架：`OxmlElement` 封装
- 写 `render/docx.py` 最小版：标题、段落
- 写 `test_ooxml_probe.py` 第一个探针
- 手工用 Word 打开验证

**交付**：能生成含标题和段落的 docx。

### W1：基础渲染（1~2 周）

**目标**：标题、正文、粗体、斜体、删除线、行内代码。

- 行内样式引擎：栈式解析 + 样式叠加
- 字体 eastAsia 设置（统一 `apply_font` 入口）
- 颜色、上下标
- 代码块渲染（基础）
- 不变量测试：config 声明值 == 输出属性

**交付**：简单报告 docx，样式与 config 一致。

### W2：行内样式 + 数学（2~3 周）

**目标**：完整行内样式 + 数学渲染。

- 数学引擎接口：`math.engine`、`math.on_fail`
- `latex2mathml` → MML2OMML.XSL → OMML
- 图片降级（matplotlib）
- 测试集：30~50 条公式
- 行内公式与块级公式
- 公式编号（依赖编号体系，可延后）

**交付**：含公式的报告 docx，公式可编辑。

### W3：编号 / 题注 / 交叉引用（2~3 周）

**目标**：标题自动编号、图/表/公式题注、交叉引用。

- 标题多级编号走 `numbering.xml`
- 图/表题注：`SEQ` 域 + `STYLEREF` 章节前缀
- 公式编号：无边框三列表格
- 交叉引用：`REF` 域，正文 `[[ref:fig1]]`
- `settings.xml` 加 `<w:updateFields w:val="true"/>`
- 编号映射显式化：heading level → ilvl → style key

**交付**：含编号和交叉引用的报告。

### W4：表格 / 图片 / 脚注（2~3 周）

**目标**：完整表格、图片、脚注。

- 表格：合并（colspan/rowspan）、固定列宽、重复表头、三线表
- 斜线表头（IR 预留，渲染可选）
- 图片：尺寸、对齐、题注
- 脚注：手写 `word/footnotes.xml`
- cell 内 block 序列（最多 2 层）

**交付**：含表格、图片、脚注的完整内容报告。

### W5：分节 / 页码 / 页眉页脚 / 目录（3~4 周）

**目标**：完整论文结构。

- 分节：`sectPr`、`[[sections]]` config
- 页码体系：前置罗马，正文阿拉伯，重启
- 页眉页脚：继承规则，正文节 `is_linked_to_previous=False`
- 封面：垂直居中走 `sectPr` 的 `w:vAlign`
- 目录：TOC 域，`TOC 1..9` 样式
- `updateFields` 确保打开自动更新

**交付**：完整论文 docx，分节、页码、页眉页脚、目录正确。

### W6：打磨 + 预设库 + 文档（1~2 周）

**目标**：可分发工具。

- `docgen init --preset=xxx`
- 预设库：竞赛技术报告、课程实验报告、论文初稿
- 用户文档：DFM 语法、config 参考、模板说明
- 示例库
- 视觉回归测试（LibreOffice headless）
- 打包、发布

**交付**：v1.0 可分发版本。

---

## 10. 测试策略

### 10.1 三层金字塔

| 层 | 内容 | 稳定性 |
|---|---|---|
| **IR 快照** | 语义层，纯 Python | 稳定 |
| **OOXML 语义探针** | 只断言 Word 专有结构：sectPr / 域 / 编号引用 | 稳定 |
| **视觉 diff** | LibreOffice headless → PDF → 栅格 diff | 最终门禁 |

**不要全文快照 `document.xml`**（脆弱：属性顺序、python-docx 版本差异）。

### 10.2 验收矩阵

- **Word 2016 / 2019 / 365 + WPS** 人工核对
- **Linux CI**：LibreOffice headless → PDF → 图像感知 diff
- **字体替换**：CI 环境需装中文字体（思源、宋体替代）

### 10.3 Phase 0 产出 = 需求覆盖矩阵

把机构格式细则逐条拆成**可测断言**。golden 文档是“样例”，覆盖矩阵是“验收”。

### 10.4 LLM 端到端测试

- 30 份 LLM 生成的 DFM 喂进 docgen，测解析成功率
- 验收标准：
  - 简单场景 ``` 使用率 > 95%
  - 嵌套场景 `\begin{code}` 使用率 > 90%
  - `\begin` 首尾名字一致率 > 95%

### 10.5 不变量测试

- 输出中每个样式属性 == config 声明值
- 写成测试，让“config 驱动”从口号变断言

---

## 11. CLI 扩展

```bash
docgen build input.md -c config.toml -o output.docx
docgen build input.md -c config.toml -o output.html --format=html
docgen check input.md -c config.toml [--json]
docgen dump-ir input.md
docgen dump-styles -c config.toml [--raw]
docgen dump-ooxml output.docx [--part=document.xml]
docgen init --preset=oi-report
docgen format input.md
```

**退出码**：
- 0 成功
- 1 内容错误
- 2 配置错误
- 3 内部错误

**`check --json` 输出**：
```json
{
  "ok": false,
  "errors": [
    {"file": "input.md", "line": 12, "col": 3, "code": "E3001", "message": "未闭合的标记"}
  ]
}
```

---

## 12. 错误码扩展

| 码 | 含义 |
|---|---|
| E1001 | 循环继承 |
| E1002 | 继承深度超限 |
| E1003 | 引用不存在的样式 |
| E2001 | 未知语言 |
| E2010 | keywords 值非法（`true` 或非字符串非 false） |
| E3001 | `\begin` 未闭合 |
| E3002 | `\begin` 首尾名字不一致 |
| E4001 | 语法错误 |
| E5001 | 母版缺失/版本不符 |
| E5002 | 数学转换失败 |
| E5003 | 分节配置错误 |
| E5004 | 编号引用不存在 |

---

## 13. 验收标准

- [ ] `docgen build` 能生成 docx
- [ ] 标题自动编号、图/表/公式题注、交叉引用正确
- [ ] 表格合并、固定列宽、重复表头正确
- [ ] 脚注可用
- [ ] 数学公式可编辑，通率 > 90%（测试集）
- [ ] 分节、页码、页眉页脚正确
- [ ] 目录域打开自动更新
- [ ] 不变量测试全绿
- [ ] OOXML 探针全绿
- [ ] 视觉回归在 Word 2016/2019/365 + WPS 人工核对通过
- [ ] LLM DFM 端到端成功率达标
- [ ] `docgen check --json` 可用
- [ ] 预设库可用
- [ ] 文档齐全
- [ ] CI 全绿

---

## 14. 母版要求

### 14.1 优秀母版特征

- 样式 id 全覆盖：`Heading1`~`Heading9`、正文、题注、脚注、页眉、页脚、目录 1~9、表格文字、代码块
- 每个 Heading 带 `w:outlineLvl`
- `numbering.xml` 已定义多级编号
- 分节骨架就位，页眉页脚占位清晰
- `TOC 1..9` 样式显式定义
- 一切格式值都是“默认值”，会被 config 覆盖
- `basedOn` 链清晰且浅
- 无隐藏样式、无残留样式
- `styleId` 稳定、语义化
- 无宏、无外部链接、无修订
- `settings.xml` 带 `<w:updateFields w:val="true"/>`
- 每个样式 `w:rFonts` 四属性齐全（ascii/hAnsi/eastAsia/cs）
- `docGrid` 与 `snapToGrid` 合理
- 分节页眉页脚继承规则明确
- 解包为 XML 入库，CI 可重建
- 带 `template_version`
- 最小化：只放必要的
- 可被自动化验证

### 14.2 坏母版特征

- 样式 id 是中文或自动生成
- 标题无 `outlineLvl`
- 只有 Normal，其他靠手动格式
- `basedOn` 链过深
- 母版里已有大量示例内容
- 无 `updateFields`
- `eastAsia` 字体缺省
- 分节页眉页脚继承混乱
- 带宏、带外部链接
- 用 WPS 私有扩展
- 母版版本无标记

### 14.3 Phase 0 母版校准清单

- [ ] 标题 1~9 样式 id 规范、`outlineLvl` 齐全
- [ ] `numbering.xml` 多级编号就绪
- [ ] `TOC 1..9` 样式显式定义
- [ ] 分节骨架完整，页眉页脚占位清晰
- [ ] 正文节 `is_linked_to_previous=False`
- [ ] `settings.xml` 带 `updateFields`
- [ ] 所有样式 `rFonts` 四属性齐全
- [ ] `docGrid` / `snapToGrid` 明确
- [ ] `basedOn` 链浅、清晰
- [ ] 无宏、无外部链接、无修订
- [ ] 解包入库、CI 可重建
- [ ] `template_version` 已打
- [ ] 能跑通不变量测试
- [ ] Word 2016/2019/365 + WPS 打开正常

---

## 15. 风险与对策

| 风险 | 影响 | 对策 |
|---|---|---|
| 开发 Linux / 目标 Windows + Word/WPS | 字体度量与渲染不同 | 人工验收清单 |
| 母版诱导绕过 config | 唯一真源被破坏 | 不变量测试 + 文档明令 |
| 数学转换失败率高 | 公式缺失 | 引擎可插拔 + `on_fail=error` + 日志 |
| 中文 eastAsia 遗漏 | 字体不生效 | 统一 `apply_font` 入口 |
| 分节页眉页脚继承混乱 | 页脚错乱 | 正文节强制 `is_linked_to_previous=False` |
| config 冻结后不够用 | 需改代码 | 分层冻结 + `ext.*` |
| LLM 生成的 DFM 不合规 | 解析失败 | `docgen check --json` + `docgen format` |
| 继承链过长/循环 | 展开失败 | 深度上限 + 环检测 + 清晰报错 |
| `\begin` 与数学冲突 | 解析歧义 | 数学内不识别 + 独占一行 |
| 视觉验收不可自动化 | 人工成本高 | CI 近似 + 人工关键节点 |
| 范围蔓延 | 项目烂尾 | 守不做清单 |
| W5 分节卡住 | 进度延误 | 单独留 3~4 周，提前 spike |

---

## 16. 明确不做

**产品层**：
- 不做 PDF 渲染器
- 不做所见即所得
- 不做 GUI
- 不做实时预览
- 不做多语言 UI
- 不做导入器（IR 层预留，不实现）

**范围层**：
- 不做公式交叉引用（题注引用可做，`\ref` 公式不做）
- 不做参考文献 BibTeX/CSL
- 不做插件系统
- 不做支持所有语言
- 不做语言检测、自动识别伪代码
- 不做语法解析（只做词法高亮）
- 不做深合并、多继承、条件继承、动态继承
- 不做跨命名空间继承
- 不做 `@keyword[color=X]` 迷你语法
- 不做 `disable_keywords` 字段
- 不做性能目标
- 不做 PDF/UA、HTML 导出、i18n first-class

**机制层**：
- 不做运行时合并
- 不做全文 `document.xml` 快照
- 不做图形化配置编辑器

---

## 17. 附录

### 17.1 OOXML 陷阱

- 标题必须写 `w:outlineLvl`，否则导航窗格和目录不认
- 必须显式定义 `TOC 1..9` 样式
- `sectPr` 位置陷阱：段落级 `sectPr` 标记“本节结束”，错一个段落页眉页脚全乱
- 页眉页脚继承：正文节必须 `is_linked_to_previous = False`
- 封面垂直居中走 `sectPr` 的 `w:vAlign`，不是段落 spacing
- `<w:updateFields w:val="true"/>` 让 Word 打开自动更新域
- 首行缩进用 `w:ind firstLineChars="200"`，不用 `firstLine`
- 段前段后用 `beforeLines / afterLines`
- 固定行距时含图/公式段落单独放开
- `docGrid + snapToGrid` 影响行距
- 中英混排 `w:rFonts` 四属性全设
- 图片尺寸用物理单位（cm/inch）

### 17.2 学习资源

- ECMA-376 标准
- `python-docx` 文档
- `lxml` 文档
- `markdown-it-py` 文档
- CommonMark 规范
- Pandoc 属性语法
- Word 宏录制 + 解包 XML 对照

### 17.3 术语表

| 术语 | 含义 |
|---|---|
| DFM | DocGen Flavored Markdown |
| IR | Intermediate Representation |
| 符号表 | config 解析后的样式表 |
| 母版 | Word `.dotx` 模板 |
| `@ref` | config 中引用另一个样式 |
| `based_on` | config 中样式继承字段 |
| 浅合并 | 字段级覆盖，子表整表替换 |
| 软删除 | 用 `false` 表示禁用 |
| canonicalize | 规范化输出，确保确定性 |
| normalize | 规范化输入 |
| eastAsia | OOXML 中文字体属性 |
| firstLineChars | OOXML 首行缩进（字符单位） |
| updateFields | Word 打开时自动更新域 |
| fence | 代码块的 ``` 语法 |
| `\begin` | LaTeX 风格命名块语法 |
| STRICT / LENIENT | 两种错误处理模式 |

---

## 18. 一句话总结

**完整版 DocGen 是在剪枝版地基上，新增 Word 渲染后端的第二题。**  
IR 是稳定接口，HTML 渲染器是参照，每 2~3 周一个可交付。  
核心工作量在 OOXML 与 Word 专有行为，预计 12~19 周。  
守住不做清单，每阶段验收，可随时停。

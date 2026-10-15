# DocGen

**DFM + TOML → Word**：一个 config 驱动的纯文本排版编译器。
写两个纯文本文件（正文 + 样式表），产出样式完全由 config 决定的 `.docx`。

- 输入：`.md`（DFM 子集）+ `.toml`（样式表）
- 输出：`.docx`（直接产出 OOXML，Word 里可继续编辑）
- 每个块级节点都带源行号；`docgen check --json` 输出结构化错误
- 产出过**官方 ECMA-376 XSD** 校验，专抓「Word 静默忽略」的错误

**已实现**：块级/行内语法、样式继承与 `@ref`、诊断与结构化错误、真超链接、
数学（LaTeX→MathML→OMML）、标题多级编号（可关、缩进可配）、题注与交叉引用（REF 域）、
表格（三线表/网格/无框 + 列宽/对齐/合并/重复表头）、图片尺寸与对齐、脚注（Word 原生自动编号）、
分节/页码/页眉页脚/封面、`[output]` 输出与日志系统、`[inline]` 语义名映射、
`docgen bug-report` 报错出口。

> **当前状态：测试版 `0.1.0b1`**（熟人小范围试用）。测试全绿、覆盖率 ≈89%，
> 产出用官方 ECMA-376 XSD 校验。
> **未实现**的见 [LIMITATIONS.md](LIMITATIONS.md)（例如目录 TOC 生成、预设库）。
>
> 👉 **新手上手**：[QUICKSTART.md](QUICKSTART.md)
> **先看这个**：[LIMITATIONS.md](LIMITATIONS.md)（已知限制，含「看着像 bug 其实不是」）
> **提反馈**：[FEEDBACK.md](FEEDBACK.md)
> **要改代码**：[HANDOFF.md](HANDOFF.md)（架构、模块地图、测试策略、OOXML 硬约束）

## 安装

```bash
# 推荐：自动挑一个当前可用的软件源（内外网状态会变，脚本运行期自己试）
# 按你的终端挑一行，三个入口做同一件事：
bash scripts/setup.sh --dev            # Git Bash / macOS / Linux
pwsh scripts/setup.ps1 --dev           # Windows PowerShell / pwsh
scripts\setup.cmd --dev                # Windows cmd
```

或者手动（用标准 venv + pip）：

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

使用 `uv` 时：

```bash
uv sync --extra dev
```

## 使用

```bash
# 解析 DFM 并打印 IR（带源行号）
docgen dump-ir tests/fixtures/minimal.md

# 展开 config（继承 + @ref 全部解析成最终值）
docgen dump-styles -c tests/fixtures/minimal.toml
docgen dump-styles -c tests/fixtures/minimal.toml --raw   # 合并后的原始表

# 校验内容里的样式引用与图片路径
docgen check input.md -c config.toml
docgen check input.md -c config.toml --strict   # 追加诊断：E3001 未闭合、E2001 未知语言
docgen check input.md -c config.toml --json

# 生成 Word 文档（样式值全部来自 config）
docgen build input.md -c config.toml -o output.docx
docgen build input.md -c config.toml -o output.docx --format docx

# 输出控制（全局开关放在子命令前）：只影响终端，不影响 [output] logfile
docgen -q build input.md -c config.toml -o out.docx          # 终端只出 err
docgen -v build input.md -c config.toml -o out.docx          # 终端出 log 级
docgen -v --logfile run.log build input.md -c config.toml    # 同时写日志文件

# 出问题时的出口：打包环境 + config 摘要 + 退出码
docgen bug-report --output report.txt -c config.toml
```

**输出约定**：结果走 stdout、诊断走 stderr（`--json` 时 stdout 只有 JSON）。
日志级别是**阈值**（`log` < `warn` 默认 < `err`，`none` 全静默），
设成 `none` 只静默打印，**退出码照常返回**。详见
[docs/config.md 的 `[output]` 段](docs/config.md)。

退出码（手册 §10）：

| 码 | 含义 |
|---|---|
| `0` | 成功 |
| `1` | 内容错误（样式引用不存在、图片缺失） |
| `2` | 配置 / 文件错误（文件不存在、非法 UTF-8、版本不符、继承环/超深、`@ref` 不存在） |

## 示例

输入 `input.md`（DFM 子集）：

```markdown
# 标题

普通段落，含 **粗体**、*斜体*、~~删除~~、`code`、[链接](https://example.com)。

- 列表项
- 嵌套
  - 更深一层

> 引用

| 列 A | 列 B |
| --- | --- |
| a1 | b1 |

行内数学 $x^2$，块级：

$$
\int_0^1 x \, dx
$$

带样式 [关键字]{.keyword}。

[[img:pics/photo.png]]

[[pagebreak]]
```

`docgen dump-ir input.md` 输出（节选）：

```text
Heading(source_line=1, level=1, content=[Text(content='标题')])
Paragraph(source_line=3, content=[Text(content='普通段落，含 '), Styled(content=[Text(content='粗体')], style_name='strong'), ...])
ListBlock(source_line=5, ordered=False, items=[...])
Table(source_line=17, rows=[['列 A', '列 B'], ['a1', 'b1']])
```

语法与冲突规则见 [docs/dfm.md](docs/dfm.md)，可运行示例见 [examples/](examples/README.md)。

## 示例库

| 示例 | 演示 |
|---|---|
| [examples/minimal](examples/minimal/README.md) | 最小完整链路（含图片、数学、分页） |
| [examples/inherit](examples/inherit/README.md) | `include` / `based_on` / `@ref` / `for = false` |
| [examples/features](examples/features/README.md) | **特性矩阵**：每个特性独立一行 + 独立信号值，一眼看出哪个失效 |

## 架构与数据流

一个 IR、两个后端。解析与校验完全不知道后端是谁；渲染层只读 IR 与 config 展开值。

```
config.toml ─┐
             ├─► config 解析 ─► 符号表（include 合并 / based_on 继承 / @ref 全部展开）
content.md  ─┘        │
                      ▼
      DFM 解析（markdown-it-py + 自定义行内规则）─► raw IR（每块带 source_line）
                      ▼
              语义校验（样式引用、图片路径）─► valid IR
                      ▼
              Word 渲染（OOXML）
              ├─ 母版/样式槽位（template, template_build）
              ├─ 数学 LaTeX→MathML→OMML（math）
              ├─ 编号/题注/交叉引用（numbering）
              ├─ 表格/图片/脚注（docx, footnotes, ooxml）
              ├─ 分节/页码/页眉页脚/封面（sections）
              └─ 产出用官方 ECMA-376 XSD 自校验（ooxml_check）
                      │
                      ▼
                 output.docx
```

**三条铁律**：解析 / IR / 渲染彻底分离；唯一真源是 config；输出中每个样式属性都等于 config 声明值。

代码依赖方向：

```
cli ──► parser ──► ir
 │        │         ▲
 │        └──► config ──► validate
 ├──► output（日志/分流/logfile，不依赖渲染）
 └──► normalize
render ──► ir + config（样式值来自 config 展开值）
           render/docx ──► ir + config + template + ooxml + numbering + math + sections + footnotes
```

## 目录结构

```
src/docgen/
  cli.py            # 命令行入口（5 个子命令）、退出码、全局输出开关
  output.py         # 输出系统：级别阈值、stdout/stderr 分流、logfile
  errors.py         # 错误码常量 + DocGenError
  normalize.py      # 输入规范化（去 BOM、统一 LF）
  ir.py             # IR：frozen dataclass，块级节点都带 source_line
  canonical.py      # 金标准解析器（交叉验证用，独立实现）
  numbering.py      # 标题/公式编号、题注与交叉引用的映射
  units.py          # 长度/字号单位换算（cm/mm/in/pt/px ↔ twips/EMU）
  config.py         # TOML 加载 / include 合并 / based_on 继承 / @ref 展开 / [inline] 映射
  validate.py       # 语义校验：样式引用、图片路径 -> 内容错误列表
  diagnostics.py    # 诊断：未闭合标记、未知语言、围栏未配对
  parser/
    dfm.py          # DFM 子集 -> IR（块级）
    rules.py        # 行内规则与 wiki 白名单（img: / ref: / fn: / pagebreak / toc）
    begin_block.py  # \begin{...} 双语法与命名块
  render/
    docx.py         # Word 后端主渲染器
    ooxml.py        # 所有 OxmlElement 构造与 OOXML 陷阱（schema 顺序插入）
    ooxml_check.py  # 官方 ECMA-376 XSD 硬校验 + 结构不变量
    template.py     # 母版加载、样式槽位、outlineLvl、updateFields、字体表
    template_build.py # 从零构建母版（编号定义、目录/题注样式）
    sections.py     # 分节 / 页面设置 / 页码 / 页眉页脚 / 封面
    math.py         # LaTeX -> MathML -> OMML
    footnotes.py    # 脚注部件生成与注入
    templates/default/  # 母版资源
tests/
  fixtures/         # minimal.md full.md minimal.toml pics/photo.png
  schemas/          # 官方 ECMA-376 XSD（校验产出合法性）
  test_ir_snapshot.py test_parser_errors.py test_normalize.py test_errors.py
  test_config.py test_validate.py test_diagnostics.py test_crosscheck.py
  test_config_source_of_truth.py test_cli.py test_output.py test_output_and_inline.py
  test_feature_matrix.py test_ooxml_schema.py test_ooxml_validity.py
  test_template.py test_math.py test_numbering.py test_formula_numbering.py
  test_table_enhancements.py test_w4_media.py test_w5_sections.py
  test_renderer_anomalies.py test_heading_and_footnotes.py test_release.py …
scripts/
  setup.sh / setup.ps1 / setup.cmd      # 装依赖：自动挑一个当前可用的软件源
  package.sh / package.ps1 / package.cmd # 打「源码测试版」压缩包（tar.gz / zip）
docs/
  dfm.md config.md ir.md crosscheck.md word.md development-manual.md
examples/
  minimal/ inherit/ features/
QUICKSTART.md LIMITATIONS.md FEEDBACK.md HANDOFF.md CHANGELOG.md
```

## 开发

```bash
pytest                              # 全部测试 + 覆盖率门槛 70%（当前 ≈89%）
ruff check .                        # lint（CI 用 . 扫全仓）
ruff format --check .               # 格式检查（docs/development-manual.md 已排除，理由见 pyproject）
mypy src tests                      # 严格模式
```

CI（[.github/workflows/ci.yml](.github/workflows/ci.yml)）在 Python 3.11 / 3.12 上依次跑
`ruff check` → `ruff format --check` → `mypy` → `pytest`（含覆盖率门槛）。

### 本地环境注意

- **装依赖用 `scripts/` 下的 setup 脚本**（`setup.sh` / `setup.ps1` / `setup.cmd`
  三选一）：内外网状态会变化，脚本会依次尝试镜像 / 直连 / 代理并选出当前可用的那个
  （详见 [QUICKSTART.md](QUICKSTART.md)）。
- 同步一律带 `--frozen`：否则换个源会把 `uv.lock` 里所有 URL 改写成那个源。
- ruff 缓存要用工作区内目录：`RUFF_CACHE_DIR=.ruff-cache`。

## 契约

- DFM 子集与冲突规则：[docs/dfm.md](docs/dfm.md)
- config schema（include / based_on / @ref / for=false / `[output]` / `[inline]`）：
  [docs/config.md](docs/config.md)
- IR 节点与不变量：[docs/ir.md](docs/ir.md)
- 解析器金标准交叉验证：[docs/crosscheck.md](docs/crosscheck.md)
- Word 后端与 OOXML 陷阱：[docs/word.md](docs/word.md)
- 完整开发手册（原始规格）：[docs/development-manual.md](docs/development-manual.md)
- 错误码：手册 §11 与 [src/docgen/errors.py](src/docgen/errors.py)
- 版本变化：[CHANGELOG.md](CHANGELOG.md)
- 可测试不变量：输出里的每个内联样式声明都等于 config 的展开值
  （[test_config_source_of_truth.py](tests/test_config_source_of_truth.py) 自动验证）
- 解析器正确性：IR 与 markdown-it token 流的一次性归约结构等价
  （[test_crosscheck.py](tests/test_crosscheck.py) 全量覆盖 `full.md`）
- **OOXML 合法性**：产出的 document.xml / footnotes.xml 过官方 ECMA-376 XSD
  （[tests/schemas/](tests/schemas/README.md)，[test_ooxml_schema.py](tests/test_ooxml_schema.py)）——
  这条抓出过「Word 静默忽略」的属性/元素顺序错误

## 相关文档

| 文档 | 用途 |
|---|---|
| [QUICKSTART.md](QUICKSTART.md) | 15 分钟上手 |
| [LIMITATIONS.md](LIMITATIONS.md) | **已知限制**（含「看着像 bug 其实不是」） |
| [FEEDBACK.md](FEEDBACK.md) | 反馈模板 |
| [HANDOFF.md](HANDOFF.md) | **开发交接**：架构、模块地图、测试策略、OOXML 硬约束与踩坑 |

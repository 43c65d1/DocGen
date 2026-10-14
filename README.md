# DocGen（剪枝版 + Word 后端）

**DFM + TOML → HTML / Word**：一个 config 驱动的纯文本排版编译器。
剪枝版（第 1~5 周）做 `DFM → IR → HTML`；完整版（Hard Version，12~19 周）在同一个 IR 上
新增 Word 渲染后端。

- 输入：`.md`（DFM 子集）+ `.toml`（样式表）
- 输出：`.html`（剪枝版）或 `.docx`（完整版）
- 每个块级节点都带源行号，`docgen check --json` 用结构化错误报告问题
- 渲染层只认 IR：HTML 是参照实现，Word 是第二个消费方

> 当前进度：剪枝版第 1~5 周完成（tag `v0.1`）；完整版 **W0 完成**
> （`--format=docx` 端到端跑通、OOXML 探针 + 不变量测试、`docs/word.md`），
> 后续按 W1~W6 推进（数学、编号/题注、表格/图片/脚注、分节/页眉页脚/目录、预设库）。

## 安装

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

# 生成 HTML（样式值全部来自 config）
docgen build input.md -c config.toml -o output.html

# 生成 Word（完整版：按扩展名自动选择后端）
docgen build input.md -c config.toml -o output.docx
docgen build input.md -c config.toml -o output.docx --format docx
```

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

## 架构与数据流

```
config.toml ─┐
             ├─► config 解析 ─► 符号表（最终值）        ← 第 2 周（已完成）
content.md  ─┘        │
                      ▼
      DFM 解析（markdown-it-py + 自定义行内规则）─► raw IR   ← 第 1、3 周（已完成）
                      ▼
              语义校验（样式引用、图片路径）─► valid IR        ← 第 2 周（已完成）
                      ▼
                HTML 渲染（纯 Python + 内联样式）─► output.html   ← 第 4 周（已完成）
```

**三条铁律**：解析 / IR / 渲染彻底分离；唯一真源是 config；输出中每个样式属性都等于 config 声明值。

代码依赖方向：

```
cli ──► parser ──► ir
 │        │         ▲
 │        └──► config ──► validate
 └──► normalize
render ──► ir + config（内联样式来自 config 展开值）
```

## 目录结构

```
src/docgen/
  cli.py            # 命令行入口、退出码
  errors.py         # 错误码常量 + DocGenError
  normalize.py      # 输入规范化（去 BOM、统一 LF）
  ir.py             # IR：frozen dataclass，块级节点都带 source_line
  config.py         # TOML 加载 / include 合并 / based_on 继承 / @ref 展开
  validate.py       # 语义校验：样式引用、图片路径 -> 内容错误列表
  diagnostics.py    # 诊断：未闭合标记 E3001、未知语言 E2001、围栏未配对 E4001
  canonical.py      # 金标准交叉验证：IR 与 token 流归约成同一规范结构再比较
  units.py          # 单位换算：12pt / 16px / 1.5em -> 磅
  parser/
    dfm.py          # DFM -> IR
    rules.py        # 自研行内标记：[[img:]] [[pagebreak]] [x]{.s} $math$
  render/
    html.py         # IR -> HTML（内联样式取 config 展开值）
    css.py          # 样式表 -> CSS 选择器规则
    docx.py         # IR -> Word（完整版）
    ooxml.py        # 所有 OxmlElement 构造与 OOXML 陷阱
    template.py     # 母版加载、样式槽位、outlineLvl、updateFields
tests/
  fixtures/         # minimal.md full.md minimal.toml pics/photo.png
  test_ir_snapshot.py test_ir_dataclass.py test_parser_errors.py
  test_normalize.py test_errors.py test_config.py test_validate.py
  test_diagnostics.py test_crosscheck.py test_html_probe.py test_cli.py
docs/
  dfm.md config.md ir.md crosscheck.md
examples/
  minimal/ inherit/
CHANGELOG.md
```

## 开发

```bash
pytest                              # 204 项测试 + 覆盖率门槛 70%（当前 86%）
ruff check .                        # lint
ruff format .                       # 格式化（line-length=100）
mypy src tests                      # 严格模式
```

CI（[.github/workflows/ci.yml](.github/workflows/ci.yml)）在 Python 3.11 / 3.12 上依次跑
`ruff check` → `ruff format --check` → `mypy` → `pytest`（含覆盖率门槛）。

### 受限沙箱下的已知差异

本机在某些受限沙箱中运行时有两点差异（不影响 CI）：

- 工作区内的 `.venv`、`.tmp`、`.pytest_cache`、`.pytest-tmp` 等缓存路径不可写，
  因此本地验证改用 `.venv-dev`（`uv sync --extra dev`，并把 `UV_CACHE_DIR` 指向工作区内目录），
  ruff 用 `RUFF_CACHE_DIR=.ruff-cache`，并跳过不可读目录（见 `pyproject.toml` 的 `exclude`）。
- 加上上一条后，`ruff format --check .` 在扫描工作区根目录时会 panic；
  本地请用 `ruff format --check src tests`，CI 不受影响。

## 契约

- DFM 子集与冲突规则：[docs/dfm.md](docs/dfm.md)
- config schema（include / based_on / @ref / for=false）：[docs/config.md](docs/config.md)
- IR 节点与不变量：[docs/ir.md](docs/ir.md)
- 解析器金标准交叉验证：[docs/crosscheck.md](docs/crosscheck.md)
- Word 后端与 OOXML 陷阱：[docs/word.md](docs/word.md)
- 错误码：手册 §11 与 [src/docgen/errors.py](src/docgen/errors.py)
- 版本变化：[CHANGELOG.md](CHANGELOG.md)
- 可测试不变量：输出里的每个内联样式声明都等于 config 的展开值
  （[test_html_probe.py](tests/test_html_probe.py) 的 `test_every_inline_style_value_comes_from_config` 自动验证）
- 解析器正确性：IR 与 markdown-it token 流的一次性归约结构等价
  （[test_crosscheck.py](tests/test_crosscheck.py) 全量覆盖 `full.md`）

# DocGen 快速上手（测试版）

> 面向**拿到源码包试用的同学**。目标：15 分钟内从零到打出第一份 `.docx`。
> 本项目是「纯文本 + 样式表 → HTML / Word」的排版编译器，**不要求安装到系统**，
> 也不需要 PyPI / wheel。

---

## 0. 一句话说明它能干什么

写两个纯文本文件：

- `content.md` —— 正文（DFM 子集，类似 Markdown）
- `config.toml` —— 样式表（字体、字号、颜色、标题编号、表格样式……）

然后：

```bash
docgen build content.md -c config.toml -o out.docx
```

得到一份**样式全部来自 config** 的 Word 文档。

---

## 1. 准备环境（二选一）

**要求**：Python ≥ 3.11（推荐 3.12）。

### 方式 A：一键装（推荐，会自动挑可用软件源）

```bash
cd docgen-0.1.0b1-src
bash scripts/setup.sh --dev        # 只跑不开发的话去掉 --dev
```

脚本会**依次尝试几个来源**（镜像直连 → PyPI 直连 → 本地代理 + PyPI → 代理 + 镜像），
用真实同步验证，哪个通用哪个，成功后会告诉你是从哪个源装的。

> **为什么要这么麻烦**：内外网状态会随时间变化——同一个索引，有时直连就通、
> 有时必须走代理、有时只能换镜像。所以脚本不预设结论，运行期自己试。
> 你也可以跳过自动逻辑，直接指定：
>
> ```bash
> bash scripts/setup.sh --dev --index https://pypi.tuna.tsinghua.edu.cn/simple
> bash scripts/setup.sh --dev --proxy http://127.0.0.1:7897
> ```

### 方式 B：用标准 venv + pip

```bash
cd docgen-0.1.0b1-src
python -m venv .venv
.venv\Scripts\Activate.ps1          # Windows
# source .venv/bin/activate          # macOS/Linux
pip install -e ".[dev]"
# 装不动就换源： pip install -e ".[dev]" -i https://pypi.tuna.tsinghua.edu.cn/simple
```

> 方式 A 需要先有 `uv`：
> `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`（Windows）或
> `curl -LsSf https://astral.sh/uv/install.sh | sh`（macOS/Linux）。
> 不想装 uv 就直接用方式 B。

### 验证装好了

```bash
uv run docgen --help          # 用方式 A
# 或（已激活 venv）
docgen --help
```

应该看到 5 个子命令：`dump-ir`、`build`、`dump-styles`、`check`、`bug-report`。

---

## 2. 第一份文档（3 分钟）

用仓库自带的示例，先看效果：

```bash
uv run docgen build examples/features/content.md \
  -c examples/features/config.toml \
  -o my-first.docx
```

打开 `my-first.docx`。这个示例把**大多数特性**都塞进去了，可以当参照物。

再自己写一份最小文档：

`content.md`

```markdown
# 我的第一份文档

这是一段正文，样式由 config 决定。可以**加粗**、*斜体*、`行内代码`。

## 小节

- 列表项一
- 列表项二

| 表头 A | 表头 B |
| --- | --- |
| 1 | 2 |

公式：$E = mc^2$

脚注示例[[fn:这是一条脚注]]。
```

`config.toml`

```toml
config_version = "0.1"

[document]
font.name = "宋体"
font.size = "11pt"
line_spacing = 1.5

[styles.strong]
font.bold = true

[table]
style = "three_line"     # three_line（默认）/ grid / none
```

```bash
uv run docgen check content.md -c config.toml   # 先校验，再构建
uv run docgen build content.md -c config.toml -o out.docx
```

---

## 3. 五个命令

| 命令 | 用途 |
|---|---|
| `docgen check <in.md> -c <cfg>` | 校验内容与 config（样式引用、图片路径）。`--strict` 追加诊断；`--json` 输出结构化错误 |
| `docgen build <in.md> -c <cfg> -o <out>` | 生成文档。按 `-o` 扩展名选后端（`.docx` → Word，其余 → HTML） |
| `docgen dump-ir <in.md>` | 打印解析出的 IR（带源行号），**排查解析问题第一步** |
| `docgen dump-styles -c <cfg>` | 打印展开后的样式表（继承/`@ref` 都解析完），**排查样式没生效第一步** |
| `docgen bug-report --output r.txt` | 打包环境 + config 摘要，反馈问题时附上这个文件 |

**退出码**：`0` 成功 / `1` 内容错误 / `2` 配置或文件错误。

---

## 4. 排查问题的固定顺序

样式「改了没反应」是最高频的问题，按这个顺序查：

1. **`dump-ir`** —— 语法有没有被正确识别？（比如 `**粗体**` 是否解析成了 `Styled`)
2. **`dump-styles`** —— 值有没有正确展开？（`based_on` 继承、`@ref` 引用都在这步解析）
3. **两个后端键名不同**！这是**最容易踩的坑**：

   | 后端 | 键名风格 | 例 |
   |---|---|---|
   | Word | 点号键（嵌套） | `font.bold` / `font.color` / `font.name` |
   | HTML | 扁平键 | `font_weight` / `color` / `font_family` |

   只写 `font.bold` 时 **HTML 不会加粗**；只写 `font_weight` 时 **Word 不会加粗**。
   要两个后端都生效就得两种键都写（`examples/features/config.toml` 是范例）。
4. **内置样式名**：`**粗体**` 用的是 `strong`，不是你自己起的名字。
   可引用名：`strong` / `em` / `strike` / `sup` / `sub`（想改名用 `[inline]` 映射）。

---

## 5. 输出与日志（可选）

```toml
[output]
level = "warn"          # 终端：log | warn(默认) | err | none
logfile = ""            # 空 = 关闭；填路径则覆盖写，尾部含退出码
logfile_level = "log"   # 文件级别，独立于终端（通常更详细）
```

```bash
uv run docgen -v build content.md -c config.toml -o out.docx     # 终端详细
uv run docgen -q build content.md -c config.toml -o out.docx     # 终端只出错误
uv run docgen -v --logfile run.log build content.md -c config.toml
```

- **结果走 stdout，诊断走 stderr**（`--json` 时 stdout 只有 JSON）。
- `-q` 只收诊断、结果照常；`level = "none"` 则**完全静默**（只留退出码）。

---

## 6. 跑测试（想改代码的话）

```bash
uv run pytest                       # 全部测试，含 70% 覆盖率门槛
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
```

> 维护者注意：**别用镜像跑 `uv lock`** —— 它会把 `uv.lock` 里 500+ 处 URL 全改写成
> 镜像地址（已踩过并回滚）。装依赖用镜像没问题；改版本只需手工改锁文件里
> docgen 那一行，`uv sync` 认它。

---

## 7. 下一步看什么

| 想了解 | 看 |
|---|---|
| DFM 语法子集与冲突规则 | [docs/dfm.md](docs/dfm.md) |
| config 全部键与继承规则 | [docs/config.md](docs/config.md) |
| IR 节点与不变量 | [docs/ir.md](docs/ir.md) |
| Word/OOXML 的坑与实现细节 | [docs/word.md](docs/word.md) |
| **已知限制（务必先看）** | [LIMITATIONS.md](LIMITATIONS.md) |
| **反馈模板** | [FEEDBACK.md](FEEDBACK.md) |
| 可运行示例 | [examples/](examples/README.md) |

---

## 8. 遇到问题怎么办

1. 先看 [LIMITATIONS.md](LIMITATIONS.md) —— 很多「像 bug」的行为是**已知限制**或**设计如此**。
2. 按 [FEEDBACK.md](FEEDBACK.md) 的模板提反馈，**附上 `docgen bug-report` 的产物**。
3. 临时绕过：`docgen -v`（看详细日志）、`docgen dump-ir` / `dump-styles`（定位在解析还是样式）。

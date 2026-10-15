# 开发交接

> 面向**接手继续开发的人**。目标是让你在一两个小时内能独立改动、跑测、定位问题。
> 安装与使用见 [README.md](README.md) 与 [QUICKSTART.md](QUICKSTART.md)；

---

## 1. 项目是什么

`DFM + TOML → HTML / Word` 的排版编译器。核心主张：**样式全部来自 config，
正文是纯文本**；解析与渲染严格分离，HTML 与 Word 是同一个 IR 上的两个后端。

规模参考（会变，用 `wc -l` / `pytest --co` 看当前值）：

| | |
|---|---|
| 源码 | ≈7000 行 / 27 个模块 |
| 测试 | ≈530 个用例，覆盖率 ≈89%（门槛 70%） |
| 技术栈 | Python ≥3.11、`markdown-it-py`、`python-docx`、`lxml`、`latex2mathml` |

## 2. 十分钟跑起来

```bash
# 装依赖：按终端挑一个入口（三者等价，都会自动挑当前可用的软件源）
bash scripts/setup.sh --dev      # Git Bash / macOS / Linux
pwsh scripts/setup.ps1 --dev     # Windows PowerShell / pwsh
scripts\setup.cmd --dev          # Windows cmd

uv run pytest                    # 全绿即环境就绪
uv run docgen --help             # 5 个子命令
```

最小验证一条链路：

```bash
uv run docgen check  examples/features/content.md -c examples/features/config.toml --strict
uv run docgen build  examples/features/content.md -c examples/features/config.toml -o /tmp/a.docx
```

## 3. 架构与依赖方向

```
config.toml ─┐
             ├─► config 解析 ─► 符号表（include 合并 / based_on 继承 / @ref 全部展开）
content.md  ─┘        │
                      ▼
      DFM 解析（markdown-it-py + 自定义行内规则）─► raw IR（每块带 source_line）
                      ▼
              语义校验（样式引用、图片路径）─► valid IR
                      ▼
        ┌─────────────┴─────────────┐
        ▼                           ▼
  HTML 渲染                    Word 渲染（OOXML）
  （参照实现）                  （母版/样式槽位 → 数学 → 编号 → 表格/图片/脚注 → 分节）
```

代码依赖方向（**改动时要守住的边界**）：

```
cli ──► parser ──► ir
 │        │         ▲
 │        └──► config ──► validate
 ├──► output（日志/分流/logfile，不依赖渲染）
 └──► normalize
render ──► ir + config（渲染层不认识解析器，也不回读源文件）
```

### 三条铁律

1. **解析 / IR / 渲染彻底分离**：渲染层只认 IR；解析器不写视觉属性
   （IR 里是 `Styled(style_name="strong")`，不是"加粗"）。
2. **config 是唯一真源**：输出里每个样式属性的值都等于 config 的展开值
   （[tests/test_html_probe.py](tests/test_html_probe.py) 有自动断言）。
3. **改渲染必须先看 IR 够不够用**：不够就先改 IR，不要在渲染里读源文本。

## 4. 模块地图

| 模块 | 职责 | 什么时候动它 |
|---|---|---|
| `cli.py` | 5 个子命令、退出码、全局输出开关 | 加命令、改参数 |
| `output.py` | 日志级别阈值、stdout/stderr 分流、logfile | 改输出行为 |
| `config.py` | TOML 加载、include 合并、based_on 继承、`@ref`、`[inline]` 映射 | 加配置键 |
| `parser/dfm.py` | DFM → IR（块级） | 加语法 |
| `parser/rules.py` | 行内规则与 `[[...]]` 白名单 | 加 `[[img:]]`/`[[fn:]]` 这类标记 |
| `parser/begin_block.py` | `\begin{...}` 双语法与命名块 | 改命名块 |
| `ir.py` | 节点定义（frozen dataclass） | 加节点/字段 |
| `validate.py` | 样式引用、图片路径校验；`[inline]` 映射链报错 | 加校验规则 |
| `diagnostics.py` | 未闭合标记 / 未知语言 / 围栏未配对 | 加诊断 |
| `numbering.py` | 标题/公式编号、题注与交叉引用映射 | 改编号逻辑 |
| `render/html.py` `css.py` | HTML 后端（**参照实现**，改动最省事） | 加特性先在 HTML 侧试 |
| `render/docx.py` | Word 后端主渲染器（最大的模块） | 加 Word 特性 |
| `render/ooxml.py` | 所有 OOXML 元素构造 + **schema 顺序插入** | 加任何 OOXML 元素 |
| `render/ooxml_check.py` | 结构不变量 + **官方 ECMA-376 XSD 校验** | 校验规则 |
| `render/template.py` `template_build.py` | 母版槽位、样式、字体表、编号定义 | 改母版/样式 |
| `render/sections.py` | 分节 / 页面设置 / 页码 / 页眉页脚 / 封面 | 改版式 |
| `render/math.py` | LaTeX → MathML → OMML | 改公式 |
| `render/footnotes.py` | 脚注部件生成与注入 | 改脚注 |
| `units.py` | 长度/字号单位换算（cm/mm/in/pt/px ↔ twips/EMU） | 改单位 |
| `canonical.py` | 金标准解析器（交叉验证用，独立实现） | 改解析规则时**同步** |

契约文档（改动前先读对应的）：

- 语法：[docs/dfm.md](docs/dfm.md)　IR：[docs/ir.md](docs/ir.md)
- 配置：[docs/config.md](docs/config.md)　Word/OOXML：[docs/word.md](docs/word.md)
- 原始规格（**决策基线**）：[docs/development-manual.md](docs/development-manual.md)

## 5. 怎么改一个特性（推荐顺序）

1. **先看 IR 够不够**。不够就加节点/字段（`ir.py`），补 [docs/ir.md](docs/ir.md)。
2. **解析器**：在 `parser/` 里产出该 IR；`test_ir_snapshot.py` 会盯着快照。
3. **HTML 后端先做**：它最简单，能确认 IR 设计没问题。
4. **Word 后端**：用 `ooxml.py` 的 `insert_child()` 构造元素（**不要 `append`**，见 §7）。
5. **校验**：需要就加 `validate.py` / `ooxml_check.py` 的规则。
6. **特性矩阵**：在 [examples/features/](examples/features/README.md) 加一行 + 独立信号值，
   并在 `test_feature_matrix.py` 加一条断言。**这是本项目定位失效点的主要手段**。
7. **文档**：改对应的 `docs/*.md` 与 [CHANGELOG.md](CHANGELOG.md)。

## 6. 测试策略（这是这个项目最值钱的部分）

| 层次 | 文件 | 作用 |
|---|---|---|
| 快照 | `test_ir_snapshot.py` | IR 结构回归（纯数据比较，不做字符串比对） |
| 契约 | `test_ir_dataclass.py` | frozen/slots、`source_line` 等不变量 |
| 交叉验证 | `test_crosscheck.py` | IR 与 markdown-it token 流的一次性归约等价 |
| 特性矩阵 | `test_feature_matrix.py` | **一个特性一条断言**，哪条红就是哪个特性没生效 |
| OOXML 合法性 | `test_ooxml_schema.py` | 产出过**官方 ECMA-376 XSD** |
| OOXML 不变量 | `test_ooxml_validity.py` | 结构层面的硬约束 |
| 回归 | `test_renderer_anomalies.py`、`test_heading_and_footnotes.py`、`test_table_enhancements.py` | 用户实测报过的问题 |
| 发布 | `test_release.py` | 版本一致性、文档存在、打包清单、脚本约束 |

跑闸门（与 CI 一致）：

```bash
ruff check . && ruff format --check . && mypy src tests && pytest
```

**三条特别有用的纪律**：

- 报"某个特性失效"时，先在特性矩阵里加一行信号值，再修——这样修完能证明真的修好了。
- 动 OOXML 时**同时**跑 `test_ooxml_schema.py` 与肉眼渲染（见 §7 的验证口径）。
- **测试只检测仓库里的内容，不检测本地环境**。测试本身会上传，所以不许写
  "某个本地文件/目录在不在""git 状态如何""ignore 规则对不对""本机装没装某个程序"
  这类断言——它们对拿到仓库的人没有意义，还会因为各人布局不同而误报。
  需要本机特有条件才能验证的，用 `pytest.mark.skipif`（例：`m:oMath` 需要
  Office 的 `MML2OMML.XSL`，没有就跳过——见 `test_math.py` 的 `requires_xsl`）。
  维护者自己的笔记与流程文档请放在**被 git 忽略的目录**里，不要进仓库；
  也不要在测试里"检查它没进仓库"。

## 7. 硬约束与踩坑（动手前必读）

### OOXML

- **域标记必须在 run 里**：`w:fldChar` / `w:instrText` / `w:t` 直接挂 `w:p` 下，
  Word 判定文档损坏（报"无法打开文件"）。用 `ooxml.py` 的包装函数。
- **书签要成对且非空**：`bookmarkStart`/`bookmarkEnd` 同 id、不能是空区间，
  否则 `REF` 域报"错误！未找到引用源"。
- **元素/属性顺序有语义**：属性容器是 `xsd:sequence`，顺序错会被 Word **静默忽略**
  （不报错，但没效果）。所以一律走 `ooxml.insert_child()`，并用官方 XSD 兜底。
  这条抓出过实战 bug：`w:firstLineChars`/`w:beforeLines` 被当成元素写
  （实为属性，导致缩进与间距**从未生效**）、`w:pgNumType`/`w:vAlign`/`w:tblLayout`
  顺序错、`w:color="AUTO"` 非法（`ST_HexColor` 只认小写 `auto`）。
- **字体要登记**：`word/fontTable.xml`（python-docx 无 API，直接改部件字节）；
  代码块这类场景**只设 `rFonts` 的 ascii/hAnsi/cs**，`eastAsia` 留给样式链，
  否则中文掉字体。
- **表格列宽在 `tblGrid`**：`add_table(rows, cols)` 的 `cols` 只决定行内 `w:tc` 数量。
  要写 `w:tblW` + `w:tblLayout=fixed` + 每列 `w:gridCol`。
- **`add_section()` 会克隆上一节 `sectPr`**：`vAlign` 这类属性会泄漏到后续节，
  所以每节要**显式**设置。
- **脚注**：条目必须有 `w:footnoteRef`（Word 的编号占位），
  `vertAlign=superscript` 只加在**编号 run** 上（加在整条文本上会让脚注正文全变上标）；
  分隔符用 `w:separator` / `w:continuationSeparator` **元素**
  （不是 `w:br w:type="separator"`，那个取值非法）。

### 验证口径（别用错工具得出错误结论）

- **bundled LibreOffice 渲染 docx 会忽略右页边距**（正文/表格看起来排到页面右边界外）。
  这是渲染器局限，已用纯 python-docx 对照文档证实。**不要据此改代码。**
- **权威视觉验收**：Word COM `ExportAsFixedFormat(pdf, 17)` 导出 PDF，
  再用 pdfium 渲染成图看。
- **权威字段值**：Word COM 打开后 `Fields.Update()` 再读 `Result.Text`
  （能验 `REF`/`SEQ`/`TOC` 是否真的算出来了）。
- **DOM 结构**：`render/ooxml_check.py` 的结构校验 + `wml_schema()` 官方 XSD。

### 环境

- 配套命令与缓存目录见 [README.md](README.md) 的"本地环境注意"；
  网络源一律用 `scripts/setup.*` 自动选，别写死。
- **脚本有三个平台变体**（`.sh` / `.ps1` / `.cmd`）做同一件事，改一个就要改另两个。
  `test_release.py` 有断言逐个检查关键约束（候选来源、`--index`/`--proxy`、`--frozen`、
  拒绝未知参数、`.cmd` 必须纯 ASCII）。`.cmd` 限定 ASCII 的原因：cmd.exe 按控制台
  代码页读文件，中文注释会被读成乱码甚至当命令执行（实测踩到）。
- 改版本号要动**三处**：`pyproject.toml`、`uv.lock` 里 docgen 那一行、
  `cli.py` 的兜底常量（测试会校验一致性）。

## 8. 已知限制与不做的事

完整清单见 [LIMITATIONS.md](LIMITATIONS.md)（含"看着像 bug 其实不是"的清单）。
明确**不做**的：多列排版、文本框、艺术字、修订/批注、PDF 直接输出。
明确**还没做**的：`docgen init --preset` 预设库、`docgen format`、
视觉回归测试、公式的图片降级（matplotlib）。

`docs/development-manual.md` 里的 W0~W6 是**原始计划**，不是当前进度；
以 `docs/word.md` 的"已实现 / 仍未实现"与 [CHANGELOG.md](CHANGELOG.md) 为准。

## 9. 下一步（如果要继续做）

按价值排序的建议：

1. **视觉回归**：现在视觉问题只能靠人工看。接 LibreOffice headless 渲染对比，
   能把 §7 里那类"静默忽略"的问题自动挡住。
2. **`docgen init --preset`**：给几套常用 config（课程报告/技术报告/论文初稿），
   降低上手成本。
3. **公式图片降级**：没装 Word 的环境里公式不显示，可考虑 matplotlib 兜底。
4. **公式编号与章节联动**：目前公式编号是全局连续，没有按章分段。
5. **表格合并的边界**：`TableCell` 的 `colspan/rowspan` 已有，但缺少复杂合并的测试覆盖。

## 10. 交接清单（接手时逐条确认）

- [ ] `bash scripts/setup.sh --dev` 成功，`uv run pytest` 全绿
- [ ] 读过 §3 三条铁律与 §7 硬约束
- [ ] 能说清 HTML 与 Word 两个后端的差异（前者是参照实现）
- [ ] 知道改特性要走 `examples/features` 特性矩阵 + `test_feature_matrix.py`
- [ ] 知道验证 Word 产出要用 Word（不是 LibreOffice）
- [ ] 知道版本号要改三处

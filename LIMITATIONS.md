# 已知限制清单（测试版 0.1.0b1）

> **先读这份再用。** 下面很多条目**不是 bug，是设计边界**——看着像缺陷但改不了或暂不改。
> 每条都标了「为什么」和「怎么办」，省得你花时间排查或提重复反馈。
>
> 反馈前请先搜这份清单；如果确实是新问题，按 [FEEDBACK.md](FEEDBACK.md) 提交。

图例：**设计如此** = 有意为之，不会改；**暂不支持** = 以后可能加；**渲染器限制** = 不是本项目的锅。

---

## A. 看起来像 bug，其实是设计如此

### A1. `three_line` 三线表没有竖线

默认表格样式只有顶线、表头下线、表底线，**没有竖线**——三线表就是这么定义的。

- **怎么办**：要竖线就显式设 `[table] style = "grid"`；完全不要框线用 `"none"`。
- config 没写 `[table] style` 时，构建会向 stderr 打一次提醒（warn 级），告诉你默认用了三线表。

### A2. 标题会自动编号，手写序号会重复

`#` / `##` **默认自动编号**（H1 → `1`、H2 → `1.1`）。所以 `# 1 概述` 会显示成 `1 1 概述`。

- **怎么办**：要么去掉手写序号，要么 `[document] heading_numbering = false`。
- 关掉编号**不影响**目录域与导航窗格（`outlineLvl` 保留）。

### A3. 标题有缩进，一级标题不贴左

多级编号**自带缩进**（`left=720 twips` + `hanging=360`），这是 Word 多级列表的默认行为。

- **怎么办**：`[document] heading_indent = false` 取消缩进；
  `heading_indent.left = "1cm"` 自定义；`leftChars = 200` 按字符；
  `[styles.heading1] indent = false` 只改某一级。

### A4. `---` 是一段带下边框的空段落

不是插入一串破折号字符，而是「空段落 + 下边框」。所以：

- 在 Word 里选中它、想删掉时，删的是**一个空段落**；
- 复制到别的软件里可能变成空白而不是横线。
- 样式可配：`[document] hr.style` / `hr.color` / `hr.size`。

### A5. 扁平键不会被读取（早期 HTML 后端的写法）

本项目只产出 Word，键名用**点号嵌套键**（`font.bold` / `font.color` / `font.name`）。

- 写扁平键（`font_weight` / `color` / `font_family` / `font_size`）**不会报错，
  但也不会生效**——没有后端再去读它。移除 HTML 后端后，这是最容易误用的一处。
- **怎么办**：统一用点号键；`docgen dump-styles -c config.toml` 能看到实际读到的值。

### A6. `level = "none"` 会连正常输出一起吞掉

`[output] level = "none"` 是**完全静默**（结果也不打印），只保留退出码。
日常安静模式请用 `-q`（只收诊断、结果照常）。

### A7. 代码块语言变体要写全名

`[code_block.python]` 生效，但语言名来自围栏标记；写错语言名会**静默不生效**。

- **怎么办**：`docgen dump-styles -c config.toml` 看注册了哪些变体。

### A8. `cover = true` 不会自己产生封面内容

`cover` 只表示「这一节页面垂直居中」，不会把正文挪进封面节。

- 配了 `[[sections]]` 但正文里**没写 `[[sectionbreak]]`** 时，所有内容落进最后一节，
  前面的节只有空页——看起来像「一页空白封面」。
- **怎么办**：封面内容 → 一行 `[[sectionbreak]]` → 正文。见
  [docs/word.md](docs/word.md) 的「分节 / 页码 / 页眉页脚」。

### A9. `[document] alignment` 会连标题一起对齐

`alignment` 是**默认值**，`[styles.body]` / `[styles.headingN]` 可覆盖。
想「标题居中、正文左对齐」就显式写正文那一条，不要只设 `[document]`。

---

## B. 暂不支持

| # | 限制 | 说明 |
|---|---|---|
| B1 | **公式没有图片回退** | 需要 Word 的 `MML2OMML.XSL`（Word 自带）把 MathML 转 OMML；没装 Word 的环境里公式可能不显示 |
| B2 | **不生成修订/批注** | 只输出最终排版 |
| B3 | **无 `docgen init --preset`** | 没有一键生成 config 脚手架的预设库；请复制 `examples/minimal/config.toml` 改 |
| B4 | **无 `docgen format`** | 不提供源码格式化 |
| B5 | **无视觉回归测试** | 没有 LibreOffice headless 渲染对比；视觉问题靠人工看（见 C1） |
| B6 | **脚注只支持纯文本** | `[[fn:...]]` 里不能嵌样式/链接/公式 |
| B7 | **单元格内不支持块级内容** | 表格单元格只支持行内内容（段落/列表/公式块进不去） |
| B8 | **上标/下标字号靠 Word** | `w:vertAlign` 自带缩放；`[styles.sup]` 的字号只在显式 `[文字]{.sup}` 写法上完全可控 |
| B9 | **图片只读本地文件** | 支持 png/jpg/jpeg/gif/svg/webp/bmp；不支持远程 URL 下载 |
| B10 | **无多列排版、无文本框、无艺术字** | 明确不做 |
| B11 | **无 PDF 直接输出** | 只能出 `.docx`；要 PDF 请用 Word「另存为」或 LibreOffice 转换 |
| B12 | **无 HTML 输出** | 早期有一个 HTML 参照后端，已移除（维护成本高、需求少）。现在只产出 Word |

---

## C. 渲染器 / 环境限制（不是本项目的锅）

### C1. 用 LibreOffice 预览时右边距看起来没了

bundled LibreOffice 渲染 `.docx` 时会**忽略右页边距**，正文/表格看起来排到页面右边界外。
已用纯 python-docx 最小对照文档证实是渲染器局限。

- **怎么办**：以 **Word** 打开为准。权威视觉核对：Word 导出 PDF 后再看。

### C2. 缺字体会提示

Word 打开时可能提示缺少某个字体（例如 `Courier`）。

- 项目已尽量裁掉不用的宏样式并登记字体表；若仍提示，装对应字体即可，**不影响排版结果**。

### C3. 公式需要 Word 参与

公式走 `LaTeX → MathML → (MML2OMML.XSL) → OMML`。非 Word 环境（如纯 LibreOffice、
某些预览器）可能显示不出公式。**Word 里正常**。

---

## D. 质量与工程现状

| 项 | 现状 |
|---|---|
| 测试 | 全绿，覆盖率 **≈89%**（门槛 70%）；具体条数会随开发变化，跑 `pytest` 看当前值 |
| 静态检查 | `ruff check` / `ruff format --check` / `mypy --strict` 全绿 |
| OOXML 合法性 | 用**官方 ECMA-376 XSD** 校验产出（`tests/schemas/`），能抓出「Word 静默忽略」的错误 | |
| 平台 | 主要在 **Windows** 上开发验证；Linux/macOS 未实测 |
| 网络 | **网状态自适应**：装依赖请用 `scripts/` 下的 setup 脚本（`.sh` / `.ps1` / `.cmd` 按终端选），它会自动挑当前可用的源（镜像 / 直连 / 代理）。 |
| 版本 | 测试版，**接口与 config 键可能变**；不保证向后兼容 |

---

## E. 提交反馈前请先排除这几种

1. **样式改了没反应** → 先看 A5（两个后端键名不同），再 `dump-styles`。
2. **某个语法没被识别** → `dump-ir` 看 IR，再查 [docs/dfm.md](docs/dfm.md) 是否在支持子集内。
3. **Word 提示修复/字体** → 看 C2；先用 Word（不是 LibreOffice）复核。
4. **公式不显示** → 看 C3 / B2，确认环境里有 Word。
5. **表格没竖线** → 看 A1，这是三线表的定义。
6. **标题编号重复/有缩进** → 看 A2 / A3。

排除了以上仍不对，那大概率是真问题——请按 [FEEDBACK.md](FEEDBACK.md) 提交。

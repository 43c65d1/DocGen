# config（TOML）参考

config 是**唯一真源**：所有字号、颜色、字体都来自这里，解析器不写死任何视觉属性。
剪枝版支持单继承 `based_on`、`@引用`、`include` 合并与 `for = false` 软删除。

## 最小示例

```toml
config_version = "0.1"

[document]
font_family = "sans-serif"
font_size = "16px"
line_height = "1.6"

[styles.heading1]
font_size = "2em"
font_weight = "bold"
color = "#111"

[styles.heading2]
based_on = "heading1"     # 单继承：浅合并，子覆盖父
font_size = "1.5em"

[styles.body]
font_size = "@document.font_size"   # @引用：解析成实际值
color = "#333"

[styles.keyword]
color = "#0000FF"
font_weight = "bold"

[styles.keyword_return]
based_on = "keyword"
color = "#FF0000"

[code_block]
background = "#f5f5f5"
font_family = "monospace"

[code_block.python]
based_on = "code_block"   # 语言变体自动以 code_block 为父
color = "#222"
```

`config_version` 必须存在且等于 `0.1`，否则报 `E5001`。

## 三个命名空间

| 命名空间 | 用途 | 展开后的样式名 |
|---|---|---|
| `[document]` | 全局值（供 `@ref` 引用） | 不参与样式表，只做符号 |
| `[styles.*]` | 内容样式（标题、正文、`[文字]{.样式名}`） | `styles.heading1` 等 |
| `[code_block]` / `[code_block.<lang>]` | 代码块样式 | `code_block`、`code_block.python` |

`[code_block]` 里的**点号键**（`font.name`）会被识别为「基座属性」而不是语言变体；
语言变体只认 `[code_block.<语言>]` 这种表头写法。

## 键名：点号嵌套写法

**只有一种读取形式**：点号键（解析后是嵌套表）：

| 用途 | 例 |
|---|---|
| 字体 | `font.bold` / `font.color` / `font.name` / `font.size` / `font.italic` |
| 段落 | `line_spacing` / `first_line_chars` / `alignment` / `space_before` / `space_after` |
| 代码块 | `[code_block] background` / `border` |

### 段落间距：`space_before` / `space_after`

`[document]` 给默认值，`[styles.body]` / `[styles.headingN]` / `[styles.caption]`
按样式覆盖。两种单位：

| 写法 | 产出 | 说明 |
|---|---|---|
| `"6pt"` / `"12px"` / `"0.2cm"` / `6`（裸数字按磅） | `w:before` / `w:after` | 绝对长度，1pt = 20 twips |
| `"0.5 line"` / `"1 line"` / `"2行"` | `w:beforeLines` / `w:afterLines` | 行单位，百分之一行（0.5 行 = 50） |

```toml
[document]
space_before = "6pt"
space_after = "6pt"

[styles.heading1]
space_before = "1 line"     # 标题前空一行
space_after = "0.5 line"
```

写错单位会**报错**（`E5001`）而不是静默丢弃——「写了不生效」曾是最难查的一类问题。

**表格**：Word 的表格没有「表格前/后间距」属性，标准做法是写到**相邻段落**上。
所以 `[table]` 的间距是这么映射的：

| 配置 | 实际写到 | 效果 |
|---|---|---|
| `[table] space_before` | 表格**前**一段的段后距 | 表格与上文隔开 |
| `[table] space_after` | 表格**后**一段的段前距 | 表格与下文隔开（解决「表格底线贴正文」） |

**图片**：`[image] space_before` / `space_after` 直接作用于图片所在的段落。

行内样式（`[文字]{.样式名}`）的样式里也能写这四个段落级键
（`alignment` / `first_line_chars` / `space_before` / `space_after`），作用于所在段落。

### `alignment`：段落对齐

`[document] alignment` 是**默认值**，`[styles.body] alignment` / `[styles.headingN] alignment`
覆盖它。注意它是默认值：只设 `[document]` 时**标题也会跟着对齐**。

| 写法 | 产出 |
|---|---|
| `left` / `start` | `w:jc w:val="left"` |
| `right` / `end` | `w:jc w:val="right"` |
| `center` / `centre` | `w:jc w:val="center"` |
| `justify` / `both` | `w:jc w:val="both"` |
| 其它任何值 | 退回左对齐（不报错——对齐是纯外观，写错不该让整篇构建失败） |

**逐段对齐 / 缩进**：DFM 没有块级样式语法，但 `[文字]{.样式名}` 的样式里若写了
`alignment` 或 `first_line_chars`，会作用到**它所在的段落**。封面署名行这类需求：

```toml
[styles.body]
first_line_chars = 200      # 正文首行缩进 2 字符

[styles.signature]
first_line_chars = 0        # 署名行不缩进
alignment = "center"
```

```markdown
[学号：5120242907　姓名：官畅宇　班级：软件2406]{.signature}
```

只认这两个段落级键；间距等其它段落属性仍由正文段落统一管理。

### 题注：`[styles.caption]`

题注段落用的是 Word 内置 `Caption` 样式，所以 `[styles.caption]` 的**字体类**
属性（`font.name` / `font.size` / `font.color` / `font.bold` …）会写进该样式，
题注文字与编号一起生效。同理 `[styles.body]` 的字体类属性写进 `Normal`。

段落级键同样生效（与正文共用一套读取）：`alignment`、`first_line_chars`。

- **默认居中**：学术排版规范要求图题在图片正下方居中，模板里的 `Caption` 样式
  预置了 `w:jc=center`；想左对齐就写 `[styles.caption] alignment = "left"`。
- **与图片同页**：图片段落自动带 `keepNext`（仅当后面紧跟图题时），图题带
  `keepLines`，所以两者不会被分页拆开（详见 [docs/word.md](word.md)）。

### 有序列表编号

每个有序列表是**独立列表**，各自从 1 开始（Markdown 里两个列表就是两个列表，
Word 里也这样）。嵌套的有序列表同样独立计数。
实现上每个列表分配一个 `w:num` 实例，复用 `List Number` 样式的 `abstractNum`
（外观不变，只换计数器）。

> ⚠️ **扁平键不会被读取**：`font_weight` / `font_style` / `font_size` /
> `font_family` / `text_decoration` 这些是早期 HTML 后端的写法。
> HTML 后端已移除，写它们**不会报错，但也不会生效**——没有后端去读。
> 排查方式：`docgen dump-styles -c config.toml` 看实际展开值。
> （`tests/test_config_source_of_truth.py` 守着「config 声明了就要到产出」。）

## `[output]`：输出与日志

```toml
[output]
level = "warn"          # 终端阈值：log | warn(默认) | err | none
logfile = ""            # 空 = 关闭；相对路径按当前工作目录解析
logfile_level = "log"   # 文件阈值，**独立于终端**（通常更详细）
```

| 级别 | 含义 |
|---|---|
| `log` | 全部输出（`-v/--verbose` 等价于此） |
| `warn` | **默认**：只出警告与错误 |
| `err` | 只出错误诊断；命令**结果照常打印**（`-q/--quiet` 等价于此） |
| `none` | **完全静默**（连结果也不打印），只留退出码 |

> `none` 与 `-q` 不一样：`-q` 只是「别刷日志」，脚本仍能拿到结果；
> `none` 是「什么都别打印」，**但退出码照常返回**（0/1/2），不会被静默掉。
> 静默只针对**终端**：``logfile`` 仍按 ``logfile_level`` 照常记录。

- **分流**：命令的**结果**走 stdout（`build` 的「已生成 …」、`check` 的 `OK:`、
  `check --json` 的 JSON），**诊断**走 stderr。`--json` 时 stdout 只有 JSON。
- **logfile**：默认关闭、**覆盖写**、单文件、无滚动。头部含
  docgen / python / 平台 / config / input，尾部含退出码；
  环境变量里的 `*_TOKEN`、`*_PASSWORD` 等敏感键会被过滤。
- CLI 的 `-q` / `-v` / `--logfile` **只影响终端**，不改文件内的级别。

## `[inline]`：语义名 -> 样式名映射

Markdown/DFM 语法产出的是**语义名**（`**粗体**` → `strong` 等），默认**同名**，
所以不写 `[inline]` 时行为完全不变；写了就能重定向到任意样式：

```toml
[inline]
sup = "sup_caret"          # ^x^ 改用 [styles.sup_caret]

[styles.sup_caret]
font.size = "7pt"
font.color = "C00000"
```

| 语义名 | 触发语法 |
|---|---|
| `strong` | `**粗体**` |
| `em` | `*斜体*` |
| `strike` | `~~删除~~` |
| `sup` | `^上标^` / `[文字]{.sup}` |
| `sub` | `~下标~` / `[文字]{.sub}` |

> 重定向后**必须**声明目标样式，否则报 `E1003`，且错误信息会**暴露映射链**：
>
> ```
> E1003:^上标^ 或 [文字]{.sup} 映射到 sup_caret（来自 [inline].sup），
>       但 config 缺少 [styles.sup_caret]
> ```

内置样式名（**无需声明即可引用，但只有声明了才会有格式**）：
`strong`、`em`、`strike`、`sup`、`sub`
—— 分别对应 `**粗体**`、`*斜体*`、`~~删除~~`、`E=mc^2^`、`H~2~O`。

> ⚠️ **最常见的坑**：`**粗体**` 用的是**内置样式名 `strong`**，不是自定义名。
> config 若不声明 `[styles.strong]`，产物里**不会加粗**（内容照常输出，只是没有格式）——
> 因为「config 是唯一真源」，引擎不写死任何视觉属性。
>
> ```toml
> [styles.strong]        # ← 必须写这一段，**粗体** 才会真的粗
> font.bold = true
> ```
>
> 对照表见 [examples/features/README.md](../examples/features/README.md)。

## `include`：多文件合并

```toml
# config.toml
config_version = "0.1"
include = ["base.toml", "overrides.toml"]

[document]
font_size = "16px"
```

合并规则：

1. 按 `include` 顺序依次合并，**后者覆盖前者**；
2. 自身文件最后合并，**覆盖所有 include**；
3. 每个文件自己也可以有 `include`（递归），出现循环报 `E5001`；
4. 合并是**逐表浅合并**：`[styles.body]` 只覆盖同名的键，其它键保留。

## `based_on`：单继承

- 浅合并：父属性先铺开，子属性覆盖同名键，未提到的键保留。
- 深度上限 **8 层**，超过报 `E1002`；出现环（含自引用）报 `E1001`。
- `based_on` 指向不存在的样式报 `E5001`。
- `[code_block.<lang>]` 不写 `based_on` 时默认继承 `code_block`。

## `@ref`：引用实际值

```toml
[document]
font_size = "16px"

[styles.body]
font_size = "@document.font_size"   # -> "16px"

[styles.base]
color = "#abc"

[styles.use]
color = "@styles.base.color"        # -> "#abc"
```

- 可指向 `[document]`、`[styles.*]`、`[code_block*]` 命名空间；
- 支持链式引用（`a` 引用 `b`，`b` 引用 `document`），解析到最终值；
- 指向不存在的键报 `E1003`；循环引用报 `E1001`。

## `for = false`：软删除

```toml
[styles.base]
color = "red"
font_weight = "bold"

[styles.child]
based_on = "base"
color = false        # 删除从父继承来的 color，结果只剩 font_weight
```

## CLI

```bash
# 展开后的最终值（继承 + @ref 都已解析）
docgen dump-styles -c config.toml

# 合并后的原始表（保留 based_on 与 @ref，便于排查）
docgen dump-styles -c config.toml --raw

# 校验内容里的样式引用与图片路径
docgen check input.md -c config.toml          # 文本错误 + 退出码
docgen check input.md -c config.toml --json   # {"ok": false, "errors": [...]}
```

`check --json` 输出：

```json
{
  "ok": false,
  "errors": [
    {"file": "input.md", "line": 3, "col": 0, "code": "E1003", "message": "引用了不存在的样式: nope"}
  ]
}
```

退出码：`0` 通过；`1` 内容错误（样式引用/图片缺失）；`2` 配置错误（文件缺失、版本不符、
继承环、深度超限、`@ref` 不存在）。

## 剪枝版不支持

多继承、深合并、跨命名空间继承、`include` 指向 URL、config 变量插值（除 `@ref` 外）。

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

## 两个后端的键名

同一份 config 服务 HTML 与 Word，但两边读的键名不同：

| 后端 | 键名风格 | 例 |
|---|---|---|
| Word | 点号键（解析后是嵌套表） | `font.bold` / `font.color` / `font.name` / `font.size` |
| HTML | 扁平键 | `font_weight` / `color` / `font_family` / `font_size` |

要两个后端都生效，两种键都要写（`examples/features/config.toml` 是范例）。
HTML 侧遇到 `font` 这类嵌套表会跳过，不会产出 `font: {'bold': True}` 这种废声明。

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

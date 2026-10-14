# DocGen 示例

这个示例覆盖 **W0~W3 的全部特性**，演示「DFM + config → HTML / Word」的完整链路：

```bash
docgen check examples/minimal/content.md -c examples/minimal/config.toml --strict
docgen build examples/minimal/content.md -c examples/minimal/config.toml -o examples/minimal/output.docx
docgen build examples/minimal/content.md -c examples/minimal/config.toml -o examples/minimal/output.html
```

## 文件

| 文件 | 说明 |
|---|---|
| [content.md](content.md) | DFM 内容：标题、段落、列表、引用、代码块（fence 与 `\begin{code}`）、表格、上下标、行内/块级/编号公式、题注、交叉引用、目录、图片、分页 |
| [config.toml](config.toml) | 样式表：`[document]` 全局值、`[styles.*]` 内容样式、`[code_block]` 代码块样式 |
| `output.docx` / `output.html` | 构建产物（未入库，用上面的命令生成） |

## 产物里可以看到什么

| 特性 | 在 docx 里的表现 |
|---|---|
| 标题多级编号 | `HeadingN` 绑定 `numId=100`，Word 打开自动编号 |
| 目录 | `TOC \o "1-9" \h \z \u` 域，打开时自动填充 |
| 题注 | 书签 + `SEQ 图 \* ARABIC` 域 + **Caption** 样式 |
| 交叉引用 | `REF fig:1 \h` / `REF eq:main \h` 域 |
| 公式 | `m:oMath`（OMML，Word 里可编辑）；编号公式用无边框三列表格 |
| 上下标 | `w:vertAlign`（superscript / subscript） |
| 代码块 | config 的 `background`/`border` → `w:shd` / `w:pBdr` |
| 图片 | 写入 `word/media/` |

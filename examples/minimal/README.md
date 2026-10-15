# DocGen 示例

这个示例演示「DFM + config → Word / Word」的**完整链路**：从解析、校验到两个后端产出，
覆盖大部分特性类别（想看"每个特性独立一行、失效即可见"的对照表，用
[../features/](../features/README.md)）：

```bash
docgen check examples/minimal/content.md -c examples/minimal/config.toml --strict
docgen build examples/minimal/content.md -c examples/minimal/config.toml -o examples/minimal/output.docx
docgen build examples/minimal/content.md -c examples/minimal/config.toml -o examples/minimal/output.docx
```

## 文件

| 文件 | 说明 |
|---|---|
| [content.md](content.md) | DFM 内容：标题、段落、列表、引用、代码块（fence 与 `\begin{code}`）、表格、上下标、行内/块级/编号公式、题注、交叉引用、目录、图片、分页 |
| [config.toml](config.toml) | 样式表：`[document]` 全局值、`[styles.*]` 内容样式、`[code_block]` 代码块样式 |
| `output.docx` / `output.docx` | 构建产物（未入库，用上面的命令生成） |

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
| 图片 | 写入 `word/media/`（`w:drawing`） |
| 分节 | `[[sections]]` → 两个 `w:sectPr`（不同纸张/页边距） |
| 分页 | `[[pagebreak]]` → `w:br w:type="page"` |
| 超链接 | 真正的 `w:hyperlink` + 关系项（不是样式化的文字） |

> 本示例**不含**脚注与 `[output]`/`[inline]` 配置；那几项见
> [../features/](../features/README.md)（特性矩阵）与
> [docs/config.md](../../docs/config.md)。

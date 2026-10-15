# 继承示例

演示 config 的四种能力，并说明每一步「谁覆盖谁」：

| 能力 | 在这个示例里 |
|---|---|
| `include` | `config.toml` 引入 `base.toml`，自身最后覆盖 |
| 覆盖 | `[document].font_size`：base 是 `15px`，config 改成 `16px` |
| `based_on` | `[styles.heading2]` 继承 `heading1`，只覆盖 `font_size`/`color` |
| `@ref` | `[styles.body].font_size = "@document.font_size"`，展开成 `16px` |
| `for = false` | `[styles.body].color = false` 删掉从 base 继承来的颜色 |

## 看合并结果

```bash
# 合并后的原始表（保留 based_on 与 @ref）
docgen dump-styles -c examples/inherit/config.toml --raw

# 展开后的最终值（继承链 + @ref 都已解析）
docgen dump-styles -c examples/inherit/config.toml
```

展开后应该看到：

```toml
[styles.body]
font_size = "16px"      # @ref 解析自 document

[styles.heading1]
color = "#0b3d91"       # 来自 base.toml
font_size = "2em"       # 被 config.toml 覆盖

[styles.heading2]
color = "#444444"
font_size = "1.4em"
font_weight = "bold"    # 继承 heading1
```

## 构建

```bash
docgen build examples/inherit/content.md -c examples/inherit/config.toml -o examples/inherit/output.docx
```

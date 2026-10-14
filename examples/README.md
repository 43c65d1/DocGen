# 示例库

三个可运行示例，每个都能用 `docgen` 端到端构建（`output.html` 未入库，用下面的命令生成）。

| 示例 | 演示什么 | 命令 |
|---|---|---|
| [minimal/](minimal/README.md) | 最小完整链路：DFM + config → HTML | `docgen build examples/minimal/content.md -c examples/minimal/config.toml -o examples/minimal/output.html` |
| [inherit/](inherit/README.md) | `include` / `based_on` / `@ref` / `for = false` | `docgen dump-styles -c examples/inherit/config.toml` |

构建前建议先跑严格校验：

```bash
docgen check examples/minimal/content.md -c examples/minimal/config.toml --strict
docgen check examples/inherit/content.md -c examples/inherit/config.toml --strict
```

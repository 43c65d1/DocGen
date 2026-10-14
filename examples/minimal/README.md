# DocGen 示例

这个示例演示「DFM + config → HTML」的最小完整链路：

```bash
docgen build examples/minimal/content.md -c examples/minimal/config.toml -o examples/minimal/output.html
```

## 文件

| 文件 | 说明 |
|---|---|
| [content.md](content.md) | DFM 内容：标题、段落、列表、引用、代码块、表格、数学、自研标记 |
| [config.toml](config.toml) | 样式表：`[document]` 全局值、`[styles.*]` 内容样式、`[code_block]` 代码块样式 |
| `output.html` | 构建产物（未入库，用上面的命令生成） |

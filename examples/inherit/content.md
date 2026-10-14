# 继承与覆盖

这份示例用的 config 由两个文件合并而成：`base.toml` 提供基础版式，
`config.toml` 覆盖其中几项并派生新样式。

## 合并规则一句话

> `include` 按顺序合并（后者覆盖前者），自身文件最后覆盖；样式用 `based_on` 继承，
> 子属性覆盖父属性，`@ref` 在最后统一解析成实际值。

## 观察点

- [正文段落]{.body}——它的 `font_size` 写的是 `@document.font_size`，
  最终值是 `16px`（`config.toml` 覆盖了 `base.toml` 的 `15px`）。
- 标题一的颜色来自 `base.toml`，字号被 `config.toml` 覆盖。
- 标题二通过 `based_on` 继承标题一，只改字号与颜色。
- `[styles.body].color = false` 删掉了基础样式里的颜色。

## 代码块

```python
from docgen.config import load_config, build_style_table

config = load_config("examples/inherit/config.toml")
print(build_style_table(config)["heading2"])
```

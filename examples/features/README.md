# 特性矩阵示例（debug 用）

**用途**：一眼看出「哪个特性失效了」。每个特性都有一个**信号值**——肉眼可辨、机器可断言。

```bash
docgen check examples/features/content.md -c examples/features/config.toml --strict
docgen build examples/features/content.md -c examples/features/config.toml -o examples/features/output.docx
docgen build examples/features/content.md -c examples/features/config.toml -o examples/features/output.html
```

## 为什么需要它

`examples/minimal` 是「完整链路能跑通」的样例，但**不便于定位**：一个特性失效时，
产物里往往只是「没那么粗」「颜色不对」，得逐个反查 OOXML 才知道是哪一层断了。
本示例把每个特性拆成**独立一行 + 独立信号值**，失效点直接暴露。

自动化侧对应 [tests/test_feature_matrix.py](../../tests/test_feature_matrix.py)：
**每个特性一条断言**，矩阵里哪条红，就是哪个特性没生效。

## 信号值一览

| 特性 | 输入 | 肉眼信号 | 机器信号 |
|---|---|---|---|
| 粗体 | `**x**` | 加粗 | `<w:b/>` |
| 斜体 | `*x*` | 倾斜 | `<w:i/>` |
| 删除线 | `~~x~~` | 横线 | `<w:strike/>` |
| 下划线 | `[x]{.feature_underline}` | 下划线 | `<w:u w:val="single"/>` |
| 颜色 | `[x]{.feature_color}` | **红字 C00000** | `<w:color w:val="C00000"/>` |
| 字号 | `[x]{.feature_small}` | 明显偏小 | `<w:sz w:val="16"/>`（8pt） |
| 行内代码 | `` `x` `` | 等宽 | `w:ascii="Consolas"` |
| 上标 / 下标 | `E=mc^2^` / `H~2~O` | 抬高 / 降低 | `w:vertAlign` |
| 链接 | `[x](https://…)` | **蓝色可点击** | `<w:hyperlink r:id=…>` + rels `TargetMode="External"` |
| 行内公式 | `$x^2$` | 排版公式 | `<m:oMath>` |
| 代码块语言色 | ` ```python ` | **绿色 008000** | `<w:color w:val="008000"/>` |
| 代码块语言色 | ` ```javascript ` | **暗金 B8860B** | `<w:color w:val="B8860B"/>` |
| 表格单元格格式 | 单元格里的 `**粗**` / `` `code` `` / `$x^2$` | 真的粗 / 等宽 / 公式 | 单元格内 `<w:b/>` / `Consolas` / `oMath` |
| 三线表 + 列宽 | `[table] style/col_widths` | 上下框线、列宽 3:3:4 | `w:gridCol` 比例 + `w:tblLayout fixed` |
| 题注 / 引用 | `\begin{caption}` / `[[ref:]]` | 图 1 / 式 (1) | `SEQ` / `REF` 域 + 书签 |
| 脚注 | `[[fn:…]]` | 页底脚注 | `word/footnotes.xml` |
| 分节 / 页码 / 页眉页脚 | `[[sections]]` | 两节、罗马→阿拉伯、页眉页脚 | `w:sectPr` / `w:pgNumType` / header-footer 部件 |

## 重要：Markdown 语法用的是「内置样式名」

`**粗体**` 生成的是**内置样式名** `strong`，不是自定义名：

| Markdown / DFM 写法 | IR 里的 `style_name` | config 里要声明 |
|---|---|---|
| `**粗体**` | `strong` | `[styles.strong]` |
| `*斜体*` | `em` | `[styles.em]` |
| `~~删除~~` | `strike` | `[styles.strike]` |
| `E=mc^2^` | `sup` | `[styles.sup]` |
| `H~2~O` | `sub` | `[styles.sub]` |
| `[文字]{.xxx}` | `xxx` | `[styles.xxx]` |

**config 不声明这些名字 → 没有格式可应用**：内容不会丢，但不会加粗/倾斜
（`config 是唯一真源`）。只在 config 里写 `[styles.feature_bold]` 而正文用
`**粗体**`，就是典型的「写了配置却没生效」。

## 两个后端的键名差异

同一份 config 服务两个后端，各自读自己认识的键：

| 后端 | 键名风格 | 例 |
|---|---|---|
| Word | 点号键（嵌套） | `font.bold` / `font.color` / `font.name` |
| HTML | 扁平键 | `font_weight` / `color` / `font_family` |

所以本示例的样式**两种键都写**。只写 `font.bold` 时 HTML 侧不会加粗；
只写 `font_weight` 时 Word 侧不会加粗。

## 已知未实现（不要误判为失效）

- `[table] style = "three_line"` 的**行内代码灰底**：单元格里的 `` `code` `` 用等宽字体，
  但没有额外底纹。
- 上标/下标的字号缩放交给 Word（``w:vertAlign`` 自带缩放），config 里的
  `[styles.sup] font.size` 只影响显式 `[文字]{.sup}` 的写法。

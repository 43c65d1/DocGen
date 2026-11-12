# DocGen 设计说明（历史与架构）

> 本文档记录项目的设计背景与总体架构，供接手改动的人理解「为什么是现在这样」。
> 语法、配置字段、实现细节以当前文档为准：
> [dfm.md](dfm.md) · [config.md](config.md) · [manual.md](manual.md) ·
> [ir.md](ir.md) · [word.md](word.md) · [crosscheck.md](crosscheck.md)。
>
> 项目早期有过一个只做 DFM→IR→HTML 的最小原型，用于验证解析与 IR 契约；
> 该原型已停止维护、代码已移除。现在只保留 Word（OOXML）后端。

## 1. 项目定位

DocGen 是一个 **config 驱动的纯文本 → Word 排版编译器**：

```
DFM 源文件 + config.toml  →  IR  →  校验  →  .docx（Word / OOXML）
```

- 输入是纯文本（DocGen Flavored Markdown + TOML），可 diff、可版本管理；
- 输出是真正的 `.docx`，不经过 HTML 中转，也不调用 Word 自动化；
- 视觉属性全部来自 config（唯一真源），解析器不写死任何字号/颜色/字体。

## 2. 设计原则

1. **config 是唯一真源**：样式、字号、间距、页面、页眉页脚都由 TOML 描述；
   母版只提供内置样式与默认值。
2. **解析与渲染分离**：parser 产出的 IR 不依赖 Word 概念；渲染层可替换。
3. **先校验再渲染**：结构用 ECMA-376 XSD + 语义探针校验，内容错误在构建前报出。
4. **编号可重复构建**：题注/交叉引用/文献编号在构建期计算并烘焙进产物，
   不依赖查看器的「更新域」。
5. **跨平台**：只用 Python + python-docx + 直接操作 OOXML，CI 可跑 Linux。

## 3. 架构与数据流

| 层 | 位置 | 职责 |
|---|---|---|
| 解析 | `src/docgen/parser/` | markdown-it + 自研规则，产出 IR；`begin_block` 预扫描命名块 |
| IR | `src/docgen/ir.py` | frozen dataclass 节点，全部带 `source_line` |
| 校验 | `src/docgen/validate.py`、`diagnostics.py`、`numbering.py`、`bibliography.py` | 样式/图片/编号/文献/诊断 |
| 渲染 | `src/docgen/render/` | `docx.py` 主渲染；`ooxml.py` 元素构造 + schema 顺序插入 |
| 配置 | `src/docgen/config.py` | TOML 读取、`include` 合并、继承与 `@ref` 展开 |
| CLI | `src/docgen/cli.py` | `check` / `build` / `dump-*` / `bug-report` |

数据流：`normalize → parse → IR → validate → render → .docx`；
PDF 转换（`--pdf`）是可选的收尾步骤，不属于核心链路。

## 4. 关键契约

- **DFM 语法**：[dfm.md](dfm.md)（块级/行内/命名块/标记白名单）
- **config 字段**：[config.md](config.md)；速查见 [cheatsheet.md](cheatsheet.md)
- **IR 节点与不变量**：[ir.md](ir.md)
- **Word/OOXML 实现与陷阱**：[word.md](word.md)
- **错误码与行为**：[manual.md](manual.md)

## 5. 历史权衡

- **不做 HTML 中转**：HTML 的样式模型与 Word 差异大，精确定位/分页/编号无法表达。
- **不做 Word COM 自动化**：依赖本机 Word、不可跨平台、CI 不可重复。
- **IR 用 frozen dataclass**：不可变、可校验、可测试；解析器与渲染器只通过 IR 交互。
- **域缓存值烘焙**：`SEQ`/`REF`/文献编号写真实值，WPS/预览也能看到正确编号。

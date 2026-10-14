# Changelog

本文件记录 DocGen（剪枝版）的对外可见变化。格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### 计划中

- 第 3 周可选：接入「金标准」解析器做交叉验证
- 第 5 周可选：临时 HTML → Word 输出（严格限时一天，第二题开始时删除）

## [0.1.0] - 2026-10-10

首个可交付版本：`DFM + TOML → HTML` 全链路可用，159 项测试、覆盖率 88%。

### 新增

- **IR**：全部行内/块级节点为 `frozen+slots` dataclass，块级节点带 `source_line`
- **DFM 解析**：标题、段落、嵌套列表、引用、代码块、分隔线、表格、行内/块级数学、
  `[文字]{.样式名}`、`[[img:path]]`、`[[pagebreak]]`；粗体/斜体/删除线统一为 `Styled`
- **config**：`include` 递归合并、`based_on` 单继承（深度上限 8、环检测）、
  `@ref` 跨命名空间解析、`for = false` 软删除
- **语义校验**：样式引用不存在（`E1003`）、图片缺失（`E5001`）
- **诊断**（`check --strict`）：未闭合标记（`E3001`）、未知代码语言（`E2001`）、
  代码围栏未配对（`E4001`）
- **渲染**：IR → HTML（内联样式取 config 展开值，文本与属性 HTML 转义）+ 确定性 CSS
- **CLI**：`dump-ir`、`dump-styles [--raw]`、`check [--json] [--strict]`、`build`
- **示例**：`examples/minimal`、`examples/inherit`
- **文档**：`docs/dfm.md`、`docs/config.md`、`docs/ir.md`
- **CI**：GitHub Actions 在 Python 3.11/3.12 上跑 ruff / mypy / pytest（覆盖率门槛 70%）

### 约定

- 错误码：`E1001` 循环继承、`E1002` 继承超深、`E1003` 样式/引用不存在、
  `E2001` 未知语言、`E3001` 标记未闭合、`E4001` 语法错误、`E5001` config/文件错误
- 退出码：`0` 成功、`1` 内容错误、`2` 配置/文件错误
- 解析器宽容（未闭合标记退化为字面文本、不丢内容），诊断由 `check` 负责

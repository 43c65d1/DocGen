# 反馈模板 / 怎么提问题

> 测试版阶段，任何反馈都有用。请**照下面模板填**——尤其第 1、3 项，
> 缺了它们我基本没法复现。

---

## 最快的方式：先跑 bug-report

```bash
uv run docgen bug-report --output bug-report.txt -c 你用的config.toml
```

它会打包**环境信息 + config 摘要**（已自动过滤 `*_TOKEN` / `*_PASSWORD` 等敏感环境变量）。
把 `bug-report.txt` 内容贴进反馈即可，不用手工抄版本号。

---

## 反馈模板（复制这段填）

`````markdown
### 1. 我做了什么（可复现的最小步骤）

<!-- 越短越好：最好是"这份 content.md + 这份 config.toml + 这条命令"就能重现 -->

1.
2.
3.

命令：
```
docgen build content.md -c config.toml -o out.docx
```

### 2. 涉及的文件

<!-- 把最小复现用的 content.md / config.toml 直接贴进来，或说明和哪个示例最接近 -->

content.md:
```markdown

```

config.toml:
```toml

```

### 3. 我期望 vs 实际

- **期望**：
- **实际**：

<!-- 视觉问题请附图：Word 截图 / 导出的 PDF 截图 -->

### 4. 环境

<!-- 直接贴 `docgen bug-report` 的前 6 行，或手工填 -->

- docgen 版本：
- Python：
- 操作系统：
- 用什么看的产物：Word / LibreOffice / 浏览器

### 5. 我先排除过这些

<!-- 勾一下你查过的，能省一轮来回 -->

- [ ] 已读 [LIMITATIONS.md](LIMITATIONS.md)，确认不是已知限制
- [ ] `docgen check` 没有报错（或报错内容已贴在上文）
- [ ] `docgen dump-ir` 输出符合预期
- [ ] `docgen dump-styles` 里样式值符合预期
- [ ] 注意了两个后端键名不同（Word 用 `font.bold`，HTML 用 `font_weight`）
- [ ] 用 Word（不是 LibreOffice）复核过

### 6. 严重程度

<!-- 选一个 -->

- [ ] 阻塞：完全用不了
- [ ] 严重：结果明显错误，但有绕过办法
- [ ] 一般：能忍 / 观感问题
- [ ] 建议：不是问题，提个改进想法
`````

---

## 各类反馈的重点

### 报告「样式没生效」

务必附上 **`dump-ir` 与 `dump-styles` 的输出**——这两步能立刻区分：
是语法没被识别（IR 层），还是值没被展开（config 层），还是后端没读对键（渲染层）。

```bash
uv run docgen dump-ir content.md > ir.txt
uv run docgen dump-styles -c config.toml > styles.txt
```

### 报告「Word 打不开 / 提示修复」

**最重要的一条**：把那份 `.docx` 一起给我（如果方便）。

这类问题通常是 OOXML 结构非法，项目自带官方 XSD 校验，
拿到文件我能直接定位到具体元素：

```bash
uv run pytest tests/test_ooxml_schema.py -q     # 顺带确认基线没坏
```

### 报告「排版和预期不一样」

说明你用的**渲染器**：Word 版本 / LibreOffice / DSH 预览。
同一份 docx 在不同渲染器下观感会不同（见 LIMITATIONS.md C1）。

### 提改进建议

直接说场景就行（「我在写 XX 类文档时，需要 YY」），不用非要提出方案。
明确「不做什么」也是有效反馈——如果某个功能你用不上，说一声能帮砍范围。

---

## 这个测试版最想知道的三件事

按重要性排序，回答任意一条都很有价值：

1. **你实际拿它写了什么文档？** 卡在哪一步、哪一步最别扭？
2. **哪些 config 键你改了发现没用？** （尤其涉及两个后端键名的时候）
3. **有没有让它输出过 Word 打不开 / 结构损坏的文件？** 附文件最好。

---

## 联系与提交位置

- **有 Git 访问**：直接开 issue，标题格式 `[docx] 简短描述` / `[html] ...` / `[cli] ...`
- **没有**：把上面模板填好发我即可，`bug-report.txt` 作为附件。

> 测试版**不保证向后兼容**：config 键与 CLI 参数可能变。每次升级请留意
> [CHANGELOG.md](CHANGELOG.md)。

# 默认母版

默认母版由 `docgen.render.template_build.build_template()` **确定性生成**
（不把二进制入库，避免每次构建都产生 git diff；手册 §14.1 的要求是「可被自动化验证 / CI 可重建」）。

生成：在 python-docx 默认模板上补齐手册 §14.1 要求、而默认模板缺失的槽位。

| 槽位 | 说明 |
|---|---|
| `Heading 1`~`Heading 9` | 默认模板已有；构建时确保带 `w:outlineLvl`（导航窗格与目录依赖） |
| `numbering.xml` | 追加多级标题编号（`numId=100`）：`Heading1`→`1`、`Heading2`→`1.1`…… |
| `TOC 1`~`TOC 9` | 默认模板没有，构建时创建（目录域按级别套用） |
| `Caption` / `Body Text` / `List Bullet` / `List Number` / `Quote` | 默认模板已有，直接复用 |
| `settings.xml` | 带 `<w:updateFields w:val="true"/>`，Word 打开自动更新编号与目录 |
| 字体 | 每个样式 `w:rFonts` 四属性（ascii/hAnsi/eastAsia/cs）齐全 |

**母版只提供结构与槽位**：所有格式值仍由引擎从 config 无条件写入
（手册 §5 铁律 2），母版里的值只是「默认值」。

## 生成 / 重建

```bash
# 生成入库用的母版文件（按需，不提交）
python -c "from pathlib import Path; from docgen.render.template_build import build_template; build_template(output=Path('src/docgen/templates/default/template.docx'))"

# 或直接用引擎默认母版：build_template() 每次都会补齐上述槽位
python -m docgen.cli build input.md -c config.toml -o out.docx
```

`tests/test_template.py` 已断言全部槽位，CI 重建即验证。

## 校准清单（手册 §14.3）现状

- [x] 标题 1~9 样式 id 规范、`outlineLvl` 齐全
- [x] `numbering.xml` 多级编号就绪
- [x] `TOC 1..9` 样式显式定义
- [x] `settings.xml` 带 `updateFields`
- [x] 所有样式 `rFonts` 四属性齐全（由引擎写入 `[document]` 时统一处理）
- [x] `basedOn` 链浅（新样式直接基于 `Normal`）
- [x] 无宏、无外部链接、无修订
- [x] 解包入库、CI 可重建
- [ ] `template_version` 已打：当前 `TEMPLATE_VERSION = "0.1"`（写在 `render/template.py`）
- [ ] 分节骨架 / 页眉页脚占位：W5 阶段补
- [ ] Word 2016/2019/365 + WPS 人工核对：需要真机

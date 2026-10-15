"""config 是唯一真源：**每个**声明的样式值都必须真的到达产出。

对应原来由 HTML 后端承担的不变量（`test_html_probe.py` 的
`test_every_inline_style_value_comes_from_config`）。HTML 后端移除后，
这条保障改由 docx 侧承担——而且更贴合真实产品路径。

方向说明（为什么不照搬 HTML 版）：
- HTML 版断言「输出里的样式声明 ⊆ config 展开值」。
- docx **不满足**那个方向：渲染器有内置兜底值（超链接 ``0563C1``、
  行内代码底纹 ``F2F2F2``），它们不来自 config。
- 对 docx 真正要守的是**反向**：config 里声明的样式值必须出现在产出里。
  这正是本项目最常见的失效模式——「config 加了样式却不生效」
  （历史上 ``w:firstLineChars``/``w:beforeLines`` 被当元素写就属此类，
  Word 静默忽略、不报错）。

覆盖范围只取**文档保证有效**的样式名（见 `docs/config.md`）：
标题、正文、`strong`/`em`/`strike`、`[文字]{.关键字}`、`[code_block]`。
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

from docgen.config import build_style_table, load_config
from docgen.parser.dfm import parse_dfm
from docgen.render.docx import render_docx_bytes

#: 每个样式给一个**独一无二**的信号颜色，避免互相遮蔽、也便于定位漏掉哪个。
#: 值必须是 OOXML 的 ``ST_HexColor``（6 位十六进制、不带 #）。
SIGNAL_CONFIG = """\
config_version = "0.1"

[document]
font.name = "宋体"
font.size = "12pt"

[styles.heading1]
font.color = "111111"

[styles.heading2]
font.color = "222222"

[styles.strong]
font.color = "333333"

[styles.em]
font.color = "444444"

[styles.strike]
font.color = "555555"

[styles.keyword]
font.color = "666666"

[styles.body]
font.color = "AAAAAA"

[code_block]
font.color = "BBBBBB"
"""

CONTENT = """\
# 一级标题

## 二级标题

正文段落，含 **粗体**、*斜体*、~~删除~~、[关键字]{.keyword} 与普通文字。

```python
print(1)
```
"""

#: 文档保证有效的样式名 → config 里给它的信号颜色
SIGNAL_COLORS = {
    "heading1": "111111",
    "heading2": "222222",
    "strong": "333333",
    "em": "444444",
    "strike": "555555",
    "keyword": "666666",
    "body": "AAAAAA",
    "code_block": "BBBBBB",
}


def _parts(tmp_path: Path) -> tuple[str, str]:
    config_path = tmp_path / "config.toml"
    config_path.write_text(SIGNAL_CONFIG, encoding="utf-8")
    data = render_docx_bytes(parse_dfm(CONTENT), load_config(config_path), base_dir=tmp_path)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        document = archive.read("word/document.xml").decode("utf-8")
        styles = archive.read("word/styles.xml").decode("utf-8")
    return document, styles


def test_every_declared_style_color_reaches_the_output(tmp_path: Path) -> None:
    """config 里声明的**每个**样式颜色都要真的出现在产出里。

    宽松处：只要求出现在 docx 的某个部件（document.xml 直接格式化，
    或 styles.xml 母版槽位）。
    严格处：**一个都不许悄无声息地丢掉**——丢掉就意味着「config 加了样式没生效」。
    """
    document, styles = _parts(tmp_path)
    combined = document + styles
    missing = {
        name: color for name, color in SIGNAL_COLORS.items() if f'w:val="{color}"' not in combined
    }
    assert not missing, f"这些样式的 config 颜色没到达产出：{missing}"


def test_declared_styles_show_up_in_document_xml_not_only_styles_xml(tmp_path: Path) -> None:
    """行内语义样式必须**直接落在正文 run 上**，不能只躺在 styles.xml 里。

    只进 styles.xml 等于「样式定义了但没被引用」——这是最隐蔽的失效方式：
    Word 打开看得到样式表里有它，正文却毫无格式。
    """
    document, _ = _parts(tmp_path)
    inline = ("333333", "444444", "555555", "666666")  # strong/em/strike/keyword
    missing = [color for color in inline if f'w:val="{color}"' not in document]
    assert not missing, f"这些行内样式没落在正文 run 上：{missing}"


def test_document_font_from_config_is_registered(tmp_path: Path) -> None:
    """`[document] font.name` 要登记进样式，而不是只有声明的空壳。"""
    _, styles = _parts(tmp_path)
    assert "宋体" in styles, "[document] 字体没进 styles.xml"


def test_every_signal_style_expands_with_the_declared_value(tmp_path: Path) -> None:
    """展开表是渲染层取值的唯一来源，所以「声明 → 展开」必须保真。

    这条是入口检查：如果连展开都丢了/变形了，后面渲染再对也没用。
    """
    config_path = tmp_path / "config.toml"
    config_path.write_text(SIGNAL_CONFIG, encoding="utf-8")
    table = build_style_table(load_config(config_path))

    for name in SIGNAL_COLORS:
        assert name in table, f"样式 {name} 没有出现在展开表里"
    # 展开值要与声明一致（只查颜色，避免耦合其它键的嵌套形状）。
    # 注意不带 `#`：Word 侧键名是 OOXML 的写法（见 docs/word.md）
    assert table["heading1"]["font"]["color"] == "111111"
    assert table["keyword"]["font"]["color"] == "666666"
    assert table["strong"]["font"]["color"] == "333333"

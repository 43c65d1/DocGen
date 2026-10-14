"""HTML 渲染契约（手册 §9：探针只断言关键结构，不做全文快照）。

三条铁律之一：渲染层只认 IR，不碰原始 DFM 标记；样式值只能来自 config。
"""

import re
from pathlib import Path

from docgen.config import load_config
from docgen.parser.dfm import parse_dfm
from docgen.render.html import render_html

FIXTURES = Path(__file__).parent / "fixtures"

CONFIG = """\
config_version = "0.1"

[document]
font_family = "sans-serif"
font_size = "16px"

[styles.heading1]
font_size = "2em"
font_weight = "bold"
color = "#111"

[styles.caption]
color = "#666"
font_size = "0.9em"

[styles.keyword]
color = "#0000FF"
font_weight = "bold"

[code_block]
background = "#f5f5f5"
font_family = "monospace"
"""


def _render(markdown: str, tmp_path: Path | None = None, full: bool = False) -> str:
    config_path = tmp_path / "config.toml" if tmp_path else FIXTURES / "minimal.toml"
    if tmp_path is not None:
        config_path.write_text(CONFIG, encoding="utf-8")
    config = load_config(config_path)
    return render_html(parse_dfm(markdown), config, title="测试文档", full_document=full)


def test_heading_becomes_h_tag(tmp_path: Path) -> None:
    out = _render("# 标题一\n\n## 标题二\n", tmp_path)
    assert "<h1" in out and ">标题一</h1>" in out
    assert "<h2" in out and ">标题二</h2>" in out


def test_heading_carries_config_values(tmp_path: Path) -> None:
    out = _render("# 标题\n", tmp_path)
    assert "font-size: 2em" in out
    assert "font-weight: bold" in out
    assert "color: #111" in out


def test_paragraph_and_inline_markup(tmp_path: Path) -> None:
    out = _render("段落 **粗** *斜* ~~删~~ `code` [链接](https://e.com)。\n", tmp_path)
    assert "<p>" in out
    assert "<strong" in out and "</strong>" in out
    assert "<em" in out
    assert "<del" in out
    assert "<code>code</code>" in out
    assert '<a href="https://e.com">链接</a>' in out


def test_html_special_characters_are_escaped(tmp_path: Path) -> None:
    out = _render('a < b & c > d "quoted"\n', tmp_path)
    assert "&lt;" in out and "&amp;" in out and "&gt;" in out


def test_styled_node_uses_config_style(tmp_path: Path) -> None:
    out = _render("[关键字]{.keyword}\n", tmp_path)
    assert "color: #0000FF" in out
    assert "font-weight: bold" in out
    assert "关键字" in out


def test_unknown_style_renders_content_without_style(tmp_path: Path) -> None:
    """内容不能因为样式缺失而丢失（check 负责报错）。"""
    out = _render("[文字]{.nope}\n", tmp_path)
    assert "文字" in out
    assert "nope" not in out


def test_unordered_and_ordered_lists(tmp_path: Path) -> None:
    out = _render("- 甲\n- 乙\n\n1. 一\n2. 二\n", tmp_path)
    assert out.count("<ul>") == 1
    assert out.count("<ol>") == 1
    assert out.count("<li>") == 4
    assert "<li>甲</li>" in out


def test_nested_list(tmp_path: Path) -> None:
    out = _render("- 父\n  - 子\n", tmp_path)
    assert "<ul>" in out
    assert out.count("<ul>") == 2
    assert "父" in out and "子" in out


def test_block_quote_contains_paragraphs(tmp_path: Path) -> None:
    out = _render("> 引用一\n>\n> 引用二\n", tmp_path)
    assert "<blockquote>" in out
    assert out.count("<p>") == 2


def test_code_block_with_language_class(tmp_path: Path) -> None:
    out = _render("```python\nprint(1)\n```\n", tmp_path)
    assert '<code class="language-python">' in out
    assert "print(1)" in out
    assert "background-color: #f5f5f5" in out
    assert "font-family: monospace" in out


def test_code_block_without_language_has_no_class(tmp_path: Path) -> None:
    out = _render("```\nplain\n```\n", tmp_path)
    assert "<code>plain\n</code>" in out


def test_table_renders_head_and_body(tmp_path: Path) -> None:
    out = _render("| 列 A | 列 B |\n| --- | --- |\n| a1 | b1 |\n", tmp_path)
    assert "<table>" in out
    assert "<thead>" in out and "<tbody>" in out
    assert "<th>列 A</th>" in out
    assert "<td>a1</td>" in out


def test_thematic_break(tmp_path: Path) -> None:
    assert "<hr>" in _render("---\n", tmp_path)


def test_standalone_pagebreak_marker(tmp_path: Path) -> None:
    out = _render("[[pagebreak]]\n", tmp_path)
    assert '<hr class="pagebreak">' in out


def test_image_block_and_inline_image(tmp_path: Path) -> None:
    out = _render("[[img:pics/a.png]]\n\n前 [[img:b.png]] 后\n", tmp_path)
    assert out.count("<img") == 2
    assert 'src="pics/a.png"' in out
    assert 'alt=""' in out


def test_image_with_alt_text(tmp_path: Path) -> None:
    out = _render("![说明](pics/a.png)\n", tmp_path)
    assert 'alt="说明"' in out


def test_inline_math_placeholder(tmp_path: Path) -> None:
    out = _render("行内 $x^2$ 结束\n", tmp_path)
    assert '<span class="math">x^2</span>' in out


def test_block_math_placeholder(tmp_path: Path) -> None:
    out = _render("$$\nE = mc^2\n$$\n", tmp_path)
    assert '<div class="math display">' in out
    assert "E = mc^2" in out


def test_hard_break_becomes_br(tmp_path: Path) -> None:
    out = _render("第一行  \n第二行\n", tmp_path)
    assert "<br>" in out


def test_full_document_has_head_and_style(tmp_path: Path) -> None:
    out = _render("# 标题\n", tmp_path, full=True)
    assert out.startswith("<!DOCTYPE html>")
    assert "<title>测试文档</title>" in out
    assert '<meta charset="utf-8">' in out
    assert "<style>" in out
    assert "body {" in out
    assert "</html>" in out


def test_body_without_full_document_is_fragment(tmp_path: Path) -> None:
    out = _render("# 标题\n", tmp_path, full=False)
    assert "<html" not in out
    assert "<style>" not in out


def test_output_is_deterministic(tmp_path: Path) -> None:
    markdown = "# 标题\n\n[关键字]{.keyword} 与 **粗体**\n"
    first = _render(markdown, tmp_path)
    second = _render(markdown, tmp_path)
    assert first == second


def test_document_font_from_config_appears_in_css(tmp_path: Path) -> None:
    out = _render("# 标题\n", tmp_path, full=True)
    assert "font-family: sans-serif" in out
    assert "font-size: 16px" in out


def test_css_has_no_duplicate_declarations(tmp_path: Path) -> None:
    """config 的同名属性必须覆盖默认值，而不是叠加成两条声明。"""
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        'config_version = "0.1"\n\n[document]\nfont_family = "system-ui"\nfont_size = "17px"\n',
        encoding="utf-8",
    )
    document = render_html(parse_dfm("# 标题\n"), load_config(config_path), full_document=True)
    body = document.split("body {", 1)[1].split("}", 1)[0]
    assert body.count("font-family:") == 1
    assert body.count("font-size:") == 1
    assert "font-family: system-ui" in body
    assert "font-size: 17px" in body


def test_every_inline_style_value_comes_from_config() -> None:
    """可测试不变量（手册 §4）：输出里的每个样式声明都等于 config 的展开值。

    用真正的夹具（full.md + minimal.toml）跑一遍完整链路。
    """
    from docgen.config import build_style_table, load_config
    from docgen.render.html import render_html as render

    config = load_config(FIXTURES / "minimal.toml")
    blocks = parse_dfm((FIXTURES / "full.md").read_text(encoding="utf-8"))
    document = render(blocks, config, title="不变量", full_document=False)

    aliases = {
        "font_size": "font-size",
        "font_family": "font-family",
        "font_weight": "font-weight",
        "background": "background-color",
    }
    declared = {
        f"{aliases.get(key, key)}: {value}"
        for properties in build_style_table(config).values()
        for key, value in properties.items()
    }
    seen = {
        part.strip()
        for match in re.findall(r'style="([^"]*)"', document)
        for part in match.split(";")
        if part.strip()
    }
    assert seen
    assert seen <= declared


def test_full_fixture_renders_all_block_kinds() -> None:
    """full.md 覆盖所有节点：确保渲染器对每类节点都有输出（不抛异常、不漏内容）。"""
    from docgen.config import load_config
    from docgen.render.html import render_html as render

    config = load_config(FIXTURES / "minimal.toml")
    blocks = parse_dfm((FIXTURES / "full.md").read_text(encoding="utf-8"))
    document = render(blocks, config, title="全量", full_document=False)
    for expected in ("<h1", "<h2", "<ul>", "<ol>", "<blockquote>", "<pre", "<table>", "<img"):
        assert expected in document
    assert "嵌套项" in document
    assert '<hr class="pagebreak">' in document

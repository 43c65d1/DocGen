"""用户实测报告的**行为契约**（每条都对应一次真实反馈）。

1. ``---`` 分隔线应是**段落底边框**，不是一长串破折号
2. 标题多级编号要能**关掉**（``[document] heading_numbering``）
3. 页面垂直对齐**每节显式设置**（封面 center / 正文 top），不依赖「克隆后删除」
4. 段落对齐 ``alignment`` 要真的落成 ``w:jc``（文档早就这么写，但没人实现）
5. 有序列表**每个列表各自从 1 开始**（原先全文共用一个计数器）
6. ``[styles.caption]`` 要写进内置 ``Caption`` 样式（原先题注完全不吃 config）
"""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path
from typing import Any

import pytest

from docgen.config import Config, load_config
from docgen.parser.dfm import parse_dfm
from docgen.render.docx import render_docx_bytes

BASE = 'config_version = "0.1"\n\n[math]\nengine = "plain"\n'


def _render(tmp_path: Path, markdown: str, config_text: str = BASE) -> str:
    path = tmp_path / "config.toml"
    path.write_text(config_text, encoding="utf-8")
    data = render_docx_bytes(parse_dfm(markdown), load_config(path))
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return archive.read("word/document.xml").decode("utf-8")


# --------------------------------------------------------------------------
# 1. 分隔线
# --------------------------------------------------------------------------
def test_thematic_break_uses_paragraph_border(tmp_path: Path) -> None:
    """``---`` → 空段落 + ``w:pBdr/w:bottom``，产物里不该有一串破折号。"""
    document = _render(tmp_path, "上文。\n\n---\n\n下文。\n")
    assert "<w:pBdr>" in document
    assert '<w:bottom w:val="single"' in document
    assert "———" not in document
    assert "\u2014\u2014\u2014" not in document


def test_thematic_break_border_is_configurable(tmp_path: Path) -> None:
    config = BASE + '\n[document]\nhr.style = "double"\nhr.size = "12"\nhr.color = "FF0000"\n'
    document = _render(tmp_path, "上文。\n\n---\n\n下文。\n", config)
    assert 'w:val="double"' in document
    assert 'w:sz="12"' in document
    assert 'w:color="FF0000"' in document


def test_thematic_break_border_color_auto_stays_lowercase(tmp_path: Path) -> None:
    """``auto`` 必须小写：``w:ST_HexColor`` 只认小写 auto（大写会被 schema 拒）。"""
    document = _render(tmp_path, "---\n")
    assert 'w:color="auto"' in document
    assert 'w:color="AUTO"' not in document


def test_paragraph_text_has_no_border(tmp_path: Path) -> None:
    """普通段落不该被加上底边框。"""
    document = _render(tmp_path, "普通段落。\n")
    assert "<w:pBdr>" not in document


# --------------------------------------------------------------------------
# 2. 标题编号开关
# --------------------------------------------------------------------------
def test_heading_numbering_on_by_default(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text(BASE, encoding="utf-8")
    data = render_docx_bytes(parse_dfm("# 标题\n\n正文\n"), load_config(path))
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        styles = archive.read("word/styles.xml").decode("utf-8")
        numbering = archive.read("word/numbering.xml").decode("utf-8")
    assert '<w:numId w:val="100"/>' in styles  # HeadingN 绑定了编号
    assert 'w:abstractNumId="100"' in numbering


def test_heading_numbering_can_be_disabled(tmp_path: Path) -> None:
    """``heading_numbering = false`` → 标题**不**绑编号，但 outlineLvl 仍在（目录照常）。"""
    path = tmp_path / "config.toml"
    path.write_text(BASE + "\n[document]\nheading_numbering = false\n", encoding="utf-8")
    data = render_docx_bytes(parse_dfm("# 标题\n\n正文\n"), load_config(path))
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        styles = archive.read("word/styles.xml").decode("utf-8")
    heading1 = re.search(r'w:styleId="Heading1".*?</w:style>', styles, re.DOTALL)
    assert heading1 is not None
    assert "w:numPr" not in heading1.group(0), "关闭编号后 Heading1 不该再有 numPr"
    assert "outlineLvl" in heading1.group(0), "outlineLvl 与编号无关，必须保留"


def test_heading_numbering_accepts_nested_form(tmp_path: Path) -> None:
    """``heading_numbering.enabled``（点号/子表写法）同样生效。"""
    path = tmp_path / "config.toml"
    path.write_text(BASE + "\n[document]\nheading_numbering.enabled = false\n", encoding="utf-8")
    data = render_docx_bytes(parse_dfm("# 标题\n"), load_config(path))
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        styles = archive.read("word/styles.xml").decode("utf-8")
    heading1 = re.search(r'w:styleId="Heading1".*?</w:style>', styles, re.DOTALL)
    assert heading1 is not None and "w:numPr" not in heading1.group(0)


def test_numbering_toggle_helper() -> None:
    from docgen.render.template import heading_numbering_enabled

    def config(document: dict[str, Any]) -> Config:
        return Config(
            version="0.1", document=document, styles={}, code_block={}, code_blocks={}, raw={}
        )

    assert heading_numbering_enabled(config({})) is True
    assert heading_numbering_enabled(config({"heading_numbering": False})) is False
    assert heading_numbering_enabled(config({"heading_numbering": {"enabled": False}})) is False
    assert heading_numbering_enabled(config({"heading_numbering": {"enabled": True}})) is True


# --------------------------------------------------------------------------
# 3. 页面垂直对齐：每节显式
# --------------------------------------------------------------------------
SECTIONS = (
    BASE
    + """
[[sections]]
page.size = "A4"
cover = true

[[sections]]
page.size = "A4"
numbering.format = "decimal"
"""
)


def test_each_section_sets_v_align_explicitly(tmp_path: Path) -> None:
    """封面 center、正文 top——两节都**显式**写出来，不靠「克隆后删除」。"""
    document = _render(tmp_path, "# 封面\n\n# 正文\n", SECTIONS)
    aligns = re.findall(r'<w:vAlign w:val="(\w+)"/>', document)
    assert aligns == ["center", "top"], aligns


def test_v_align_absent_when_no_sections_config(tmp_path: Path) -> None:
    """没配 ``[[sections]]`` 时不主动写 vAlign（保持母版默认）。"""
    document = _render(tmp_path, "# 标题\n")
    assert "<w:vAlign" not in document


@pytest.mark.parametrize("value", ["center", "top"])
def test_v_align_is_schema_ordered(tmp_path: Path, value: str) -> None:
    """``w:vAlign`` 必须排在 ``w:docGrid`` 之前（insert_child 负责）。"""
    document = _render(tmp_path, "# 一\n\n# 二\n", SECTIONS)
    assert document.index("<w:vAlign") < document.index("<w:docGrid")


# --------------------------------------------------------------------------
# 4. 段落对齐：config 的 alignment 要真的落到 w:jc
# --------------------------------------------------------------------------
ALIGN_DOC = BASE + '\n[document]\nalignment = "right"\n'
ALIGN_BODY = BASE + '\n[document]\nalignment = "justify"\n\n[styles.body]\nalignment = "center"\n'


def test_document_alignment_applies_to_body_and_headings(tmp_path: Path) -> None:
    """``[document] alignment`` 是**默认值**：正文与标题都该跟着走。

    以前完全没人读它（文档却说它是段落键）。
    """
    document = _render(tmp_path, "# 标题\n\n正文一。\n\n正文二。\n", ALIGN_DOC)
    # 标题 1 处 + 两个正文段落
    assert re.findall(r'<w:jc w:val="(\w+)"/>', document) == ["right", "right", "right"]


def test_body_alignment_overrides_document(tmp_path: Path) -> None:
    """``[styles.body]`` 比 ``[document]`` 更具体：标题仍走 document，正文被覆盖。"""
    document = _render(tmp_path, "# 标题\n\n正文。\n", ALIGN_BODY)
    # 标题 justify → both；正文 body 覆盖成 center
    assert re.findall(r'<w:jc w:val="(\w+)"/>', document) == ["both", "center"]


def test_heading_alignment_from_heading_style(tmp_path: Path) -> None:
    """``[styles.heading1] alignment`` 覆盖 ``[document]`` 的兜底值。"""
    config = BASE + (
        '\n[document]\nalignment = "left"\n\n[styles.heading1]\nalignment = "center"\n'
    )
    document = _render(tmp_path, "# 标题\n\n正文。\n", config)
    aligns = re.findall(r'<w:jc w:val="(\w+)"/>', document)
    assert aligns == ["center", "left"], aligns


def test_justify_alignment_maps_to_both(tmp_path: Path) -> None:
    """习惯写法 ``justify`` 要映射成 OOXML 的 ``both``。"""
    document = _render(tmp_path, "正文。\n", BASE + '\n[document]\nalignment = "justify"\n')
    assert '<w:jc w:val="both"/>' in document


def test_unknown_alignment_falls_back_to_left(tmp_path: Path) -> None:
    """非法对齐值不该让构建失败（纯外观），按左对齐处理。"""
    document = _render(tmp_path, "正文。\n", BASE + '\n[document]\nalignment = "middle"\n')
    assert '<w:jc w:val="left"/>' in document


def test_alignment_already_there_when_docx_built_through_cli(tmp_path: Path) -> None:
    """走 CLI 的真实路径也要生效（上面用的是直接调渲染器）。"""
    from docgen.cli import main

    (tmp_path / "config.toml").write_text(ALIGN_BODY, encoding="utf-8")
    source = tmp_path / "doc.md"
    source.write_text("正文。\n", encoding="utf-8")
    output = tmp_path / "out.docx"
    assert main(["build", str(source), "-o", str(output)]) == 0
    with zipfile.ZipFile(io.BytesIO(output.read_bytes())) as archive:
        document = archive.read("word/document.xml").decode("utf-8")
    assert '<w:jc w:val="center"/>' in document


def test_inline_style_can_override_paragraph_indent(tmp_path: Path) -> None:
    """署名行要 0 缩进、正文要 2 字符缩进——没有块级样式语法时靠 `[文字]{.样式}`。

    实测需求：实验报告封面署名「学号/姓名/班级」一行居中、且不套正文首行缩进。
    """
    config = BASE + (
        "\n[styles.body]\nfirst_line_chars = 200\n"
        '\n[styles.signature]\nfirst_line_chars = 0\nalignment = "center"\n'
    )
    document = _render(tmp_path, "正文。\n\n[署名行]{.signature}\n", config)
    indents = re.findall(r'w:firstLineChars="(\d+)"/>', document)
    assert indents == ["200", "0"], indents
    assert '<w:jc w:val="center"/>' in document


# --------------------------------------------------------------------------
# 5. 有序列表：每个列表各自从 1 开始
# --------------------------------------------------------------------------
def _render_parts(tmp_path: Path, markdown: str, config_text: str = BASE) -> tuple[str, str]:
    """返回 (document.xml, numbering.xml)。"""
    path = tmp_path / "config.toml"
    path.write_text(config_text, encoding="utf-8")
    data = render_docx_bytes(parse_dfm(markdown), load_config(path))
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return (
            archive.read("word/document.xml").decode("utf-8"),
            archive.read("word/numbering.xml").decode("utf-8"),
        )


def test_two_ordered_lists_get_separate_numbering(tmp_path: Path) -> None:
    """两个有序列表必须是两个编号实例，否则第 2 个接着第 1 个数下去。

    原实现只挂 ``List Number`` 样式，编号来自样式自带的单个 ``numId``——
    全文共用一个计数器。

    **只换 ``numId`` 还不够**（实测）：Word 对「多个 ``w:num`` 共用同一个
    ``abstractNum``」默认接着数，必须配 ``lvlOverride/startOverride`` 才重启。
    """
    document, numbering = _render_parts(tmp_path, "1. 甲\n2. 乙\n\n中间段落\n\n1. 丙\n2. 丁\n")
    ids = re.findall(r'<w:numId w:val="(\d+)"/>', document)
    assert len(ids) == 4, ids
    assert ids[0] == ids[1], "同一个列表内的条目应共用实例"
    assert ids[2] == ids[3]
    assert ids[0] != ids[2], "两个列表不能共用一个计数器"
    for num_id in (ids[0], ids[2]):
        assert f'<w:num w:numId="{num_id}">' in numbering, "新实例要登记进 numbering.xml"
        num = re.search(rf'<w:num w:numId="{num_id}">.*?</w:num>', numbering, re.DOTALL)
        assert num is not None
        assert "startOverride" in num.group(0), "没有 startOverride，Word 会接着上一个列表数"


def test_nested_ordered_list_gets_its_own_numbering(tmp_path: Path) -> None:
    """嵌套列表也是独立列表：有序时它同样从 1 开始。"""
    document, _ = _render_parts(tmp_path, "1. 甲\n   1. 甲一\n   2. 甲二\n2. 乙\n")
    ids = re.findall(r'<w:numId w:val="(\d+)"/>', document)
    assert ids[0] == ids[3], ids  # 外层两项共用
    assert ids[1] == ids[2], ids  # 内层两项共用
    assert ids[0] != ids[1], "嵌套列表不能和外层共用计数器"


def test_bullet_list_does_not_need_numbering_instances(tmp_path: Path) -> None:
    """无序列表不参与计数，不应被塞 numPr（否则会带上多余的编号定义）。"""
    document, _ = _render_parts(tmp_path, "- 甲\n- 乙\n")
    assert "ListBullet" in document
    assert "<w:numPr>" not in document


def test_list_numbering_is_schema_ordered(tmp_path: Path) -> None:
    """``w:numPr`` 内部 ``ilvl`` 必须在 ``numId`` 之前（sequence 顺序）。"""
    document, _ = _render_parts(tmp_path, "1. 甲\n")
    numpr = re.search(r"<w:numPr>.*?</w:numPr>", document, re.DOTALL)
    assert numpr is not None
    assert numpr.group(0).index("w:ilvl") < numpr.group(0).index("w:numId")


# --------------------------------------------------------------------------
# 6. 题注样式：``[styles.caption]`` 要写进内置 Caption 样式
# --------------------------------------------------------------------------
CAPTION = BASE + (
    '\n[styles.caption]\nfont.color = "C00000"\nfont.size = "10.5pt"\nfont.name = "黑体"\n'
)


def test_caption_style_reaches_the_builtin_caption_style(tmp_path: Path) -> None:
    """题注段落用的是内置 ``Caption`` 样式，config 必须写进该样式。

    原先 ``_render_caption`` 只挂 ``style="Caption"``，``[styles.caption]``
    的声明没人读——「config 写了但不生效」。
    """
    path = tmp_path / "config.toml"
    path.write_text(CAPTION, encoding="utf-8")
    blocks = parse_dfm("\\begin{caption #fig:1}\n图题\n\\end{caption}\n")
    data = render_docx_bytes(blocks, load_config(path))
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        styles = archive.read("word/styles.xml").decode("utf-8")
    caption = re.search(r'<w:style [^>]*w:styleId="Caption".*?</w:style>', styles, re.DOTALL)
    assert caption is not None, "母版里没有 Caption 样式"
    body = caption.group(0)
    assert 'w:val="C00000"' in body, "字体颜色没写进 Caption 样式"
    assert 'w:sz w:val="21"' in body, "10.5pt 应写成半磅 21"
    assert "黑体" in body, "字体名没写进 Caption 样式"


def test_caption_style_is_neutral_without_config(tmp_path: Path) -> None:
    """没声明 ``[styles.caption]`` 时，题注不该自带母版的「加粗 + 主题蓝 9pt」。

    母版默认 Caption 是强调色，与「config 是唯一真源」冲突；中性化后它继承 Normal。
    """
    path = tmp_path / "config.toml"
    path.write_text(BASE, encoding="utf-8")
    blocks = parse_dfm("\\begin{caption #fig:1}\n图题\n\\end{caption}\n")
    data = render_docx_bytes(blocks, load_config(path))
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        styles = archive.read("word/styles.xml").decode("utf-8")
    caption = re.search(r'<w:style [^>]*w:styleId="Caption".*?</w:style>', styles, re.DOTALL)
    assert caption is not None
    body = caption.group(0)
    assert "themeColor" not in body, "题注仍带主题色"
    assert "<w:color" not in body, "题注仍自带颜色"
    assert "<w:b/>" not in body and "<w:bCs/>" not in body, "题注仍自带加粗"


# --------------------------------------------------------------------------
# 7. 中文标题字体：font.name 必须写 w:eastAsia
# --------------------------------------------------------------------------
HEADING_FONT = BASE + '\n[styles.heading1]\nfont.name = "黑体"\nfont.size = "22pt"\n'


def test_heading_font_name_writes_east_asia_on_runs(tmp_path: Path) -> None:
    """Word 对中文字符取 ``w:eastAsia``：只写 ascii/hAnsi/cs 时中文标题不换字体。"""
    document = _render(tmp_path, "# 中文标题\n", HEADING_FONT)
    fonts = re.findall(r"<w:rFonts[^>]*/>", document)
    assert fonts, "标题 run 上没有 rFonts"
    assert any('w:eastAsia="黑体"' in tag for tag in fonts), fonts


def test_code_block_does_not_force_east_asia(tmp_path: Path) -> None:
    """代码块是例外：等宽字体没有中文字形，eastAsia 必须留给样式链。"""
    document = _render(tmp_path, "```python\nprint(1)\n```\n", HEADING_FONT)
    mono = [tag for tag in re.findall(r"<w:rFonts[^>]*/>", document) if "Consolas" in tag]
    assert mono, "代码块没设等宽字体"
    assert all("eastAsia" not in tag for tag in mono), mono


# --------------------------------------------------------------------------
# 8. Heading 的**样式定义**也要吃 config（否则 Word 样式面板仍是主题蓝）
# --------------------------------------------------------------------------
def test_heading_style_definition_follows_config(tmp_path: Path) -> None:
    """只写 run 级的话，Word 里「新敲一个标题」还是母版的主题蓝。"""
    config = HEADING_FONT + 'font.color = "000000"\nfont.bold = true\n'
    path = tmp_path / "config.toml"
    path.write_text(config, encoding="utf-8")
    blocks = parse_dfm("# 中文标题\n")
    data = render_docx_bytes(blocks, load_config(path))
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        styles = archive.read("word/styles.xml").decode("utf-8")
    heading1 = re.search(r'<w:style [^>]*w:styleId="Heading1".*?</w:style>', styles, re.DOTALL)
    assert heading1 is not None
    body = heading1.group(0)
    assert 'w:val="000000"' in body, "样式定义的颜色没被 config 覆盖"
    assert "themeColor" not in body, "主题色没清掉（优先级高于显式色值）"
    assert 'w:eastAsia="黑体"' in body, "样式定义缺 eastAsia"
    assert "majorEastAsia" not in body, "主题字体属性没清掉"
    assert 'w:sz w:val="44"' in body, "22pt 应写成半磅 44"


# --------------------------------------------------------------------------
# 9. ``[[sectionbreak]]``：内容要能落到前面的节里
# --------------------------------------------------------------------------
COVER_CONFIG = BASE + (
    "\n[[sections]]\n"
    'page.size = "A4"\n'
    'numbering.format = "upperRoman"\n'
    "cover = true\n"
    "\n"
    "[[sections]]\n"
    'page.size = "A4"\n'
    'numbering.format = "decimal"\n'
    "numbering.start = 1\n"
    'footer.text = "第 PAGE 页"\n'
)


def test_sectionbreak_marker_becomes_ir_node() -> None:
    from docgen.ir import SectionBreak

    blocks = parse_dfm("封面\n\n[[sectionbreak]]\n\n正文\n")
    assert any(isinstance(block, SectionBreak) for block in blocks)


def test_sectionbreak_puts_cover_content_in_the_first_section(tmp_path: Path) -> None:
    """``cover = true`` 原先只建空节 → 一页空白封面。分节符让封面内容真的在封面节。"""
    path = tmp_path / "config.toml"
    path.write_text(COVER_CONFIG, encoding="utf-8")
    blocks = parse_dfm("封面标题\n\n[[sectionbreak]]\n\n正文段落\n")
    data = render_docx_bytes(blocks, load_config(path))
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        document = archive.read("word/document.xml").decode("utf-8")
    assert document.count("<w:sectPr") == 2
    first_break = document.index("sectPr")
    assert document.index("封面标题") < first_break, "封面内容没落在第一节"
    assert document.index("正文段落") > first_break, "正文没落在第二节"


def test_sectionbreak_without_sections_config_is_harmless(tmp_path: Path) -> None:
    """没有 ``[[sections]]`` 时写了分节符也不该崩（配置为空 = 保持单节）。"""
    document = _render(tmp_path, "A\n\n[[sectionbreak]]\n\nB\n")
    assert "A" in document and "B" in document

"""需求三项：table 默认提示、单元格行内代码灰底、`[inline]` 映射段。"""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

import pytest

from docgen import cli
from docgen.config import Config, build_style_table, build_style_tree, load_config
from docgen.errors import E_UNKNOWN_STYLE
from docgen.ir import Code, Paragraph, Styled, Table, Text
from docgen.parser.dfm import parse_dfm
from docgen.render.docx import render_docx_bytes
from docgen.render.math import find_xsl
from docgen.validate import validate_content

#: 公式产出 OMML 需要 Office 的 ``MML2OMML.XSL``；没有它时按设计降级为纯文本
#: （见 `render/math.py`），所以相关断言在无 XSL 的环境（Linux CI）跳过。
HAS_XSL = find_xsl() is not None
requires_xsl = pytest.mark.skipif(
    not HAS_XSL, reason="本机没有 MML2OMML.XSL（Office），公式按设计降级为纯文本"
)

BASE = 'config_version = "0.1"\n'

TABLE_MD = "| a | b |\n| --- | --- |\n| 1 | 2 |\n"
NO_TABLE_MD = "# 标题\n\n只有正文，没有表格。\n"


def _config(tmp_path: Path, text: str) -> Config:
    path = tmp_path / "config.toml"
    path.write_text(text, encoding="utf-8")
    return load_config(path)


def _document_xml(tmp_path: Path, markdown: str, config_text: str = BASE) -> str:
    config = _config(tmp_path, config_text)
    data = render_docx_bytes(parse_dfm(markdown), config)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return archive.read("word/document.xml").decode("utf-8")


# ==========================================================================
# 二、table 默认值提示
# ==========================================================================
def test_table_hint_when_style_not_declared(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """config 未声明 [table] style 且含表格 → stderr 打一次 warn 提示。"""
    config = tmp_path / "c.toml"
    config.write_text(BASE, encoding="utf-8")
    source = tmp_path / "a.md"
    source.write_text(TABLE_MD, encoding="utf-8")

    code = cli.main(["build", str(source), "-c", str(config), "-o", str(tmp_path / "o.html")])

    captured = capsys.readouterr()
    assert code == 0
    assert "[warn] 表格使用默认三线表样式" in captured.err
    assert 'style = "grid"' in captured.err and 'style = "none"' in captured.err
    assert captured.err.count("表格使用默认三线表样式") == 1  # 每次构建一次


def test_table_hint_absent_when_style_declared(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """显式声明（哪怕还是 three_line）就不再提示。"""
    config = tmp_path / "c.toml"
    config.write_text(BASE + '\n[table]\nstyle = "three_line"\n', encoding="utf-8")
    source = tmp_path / "a.md"
    source.write_text(TABLE_MD, encoding="utf-8")

    cli.main(["build", str(source), "-c", str(config), "-o", str(tmp_path / "o.html")])
    assert "表格使用默认三线表样式" not in capsys.readouterr().err


def test_table_hint_absent_without_tables(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """没有表格就不提示（即使没声明 style）。"""
    config = tmp_path / "c.toml"
    config.write_text(BASE, encoding="utf-8")
    source = tmp_path / "a.md"
    source.write_text(NO_TABLE_MD, encoding="utf-8")

    cli.main(["build", str(source), "-c", str(config), "-o", str(tmp_path / "o.html")])
    assert "表格" not in capsys.readouterr().err


def test_table_hint_is_suppressed_by_quiet(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """提示是 warn 级，``-q``（err 阈值）下应消失。"""
    config = tmp_path / "c.toml"
    config.write_text(BASE, encoding="utf-8")
    source = tmp_path / "a.md"
    source.write_text(TABLE_MD, encoding="utf-8")

    cli.main(["-q", "build", str(source), "-c", str(config), "-o", str(tmp_path / "o.html")])
    assert "表格使用默认三线表样式" not in capsys.readouterr().err


def test_table_style_default_is_three_line(tmp_path: Path) -> None:
    """默认值仍是三线表：无竖线、无内部横线。"""
    document = _document_xml(tmp_path, TABLE_MD)
    borders = re.search(r"<w:tblBorders>.*?</w:tblBorders>", document, re.DOTALL)
    assert borders is not None
    body = borders.group(0)
    assert '<w:top w:val="single"/>' in body
    assert '<w:bottom w:val="single"/>' in body
    assert '<w:left w:val="none"/>' in body
    assert '<w:right w:val="none"/>' in body
    assert '<w:insideV w:val="none"/>' in body


def test_declares_reports_explicit_declaration(tmp_path: Path) -> None:
    """``Config.declares`` 是「是否显式声明」的判据，支持嵌套写法。"""
    config = _config(tmp_path, BASE + '\n[table]\nstyle = "grid"\n')
    assert config.declares("table", "style") is True
    assert config.declares("table", "header_repeat") is False

    nested = _config(tmp_path, BASE + '\n[table.style]\nname = "grid"\n')
    assert nested.declares("table", "style.name") is True

    empty = _config(tmp_path, BASE)
    assert empty.declares("table", "style") is False


# ==========================================================================
# 三、单元格内 inline code 灰底
# ==========================================================================
def test_inline_code_has_run_shading_in_paragraph(tmp_path: Path) -> None:
    document = _document_xml(tmp_path, "段落里的 `code` 片段。\n")
    assert "<w:shd" in document
    assert 'w:fill="F2F2F2"' in document


def test_inline_code_has_run_shading_inside_table_cell(tmp_path: Path) -> None:
    """需求点名：**表格单元格内**的 inline code 也要有灰底。"""
    document = _document_xml(tmp_path, "| 语法 | 值 |\n| --- | --- |\n| `code` | x |\n")
    table = re.search(r"<w:tbl>.*?</w:tbl>", document, re.DOTALL)
    assert table is not None
    assert "F2F2F2" in table.group(0)


def test_inline_code_shading_is_run_level_not_paragraph(tmp_path: Path) -> None:
    """底纹必须在 run 上（``w:rPr/w:shd``）——段落底纹会涂满整行。"""
    document = _document_xml(tmp_path, "前 `code` 后。\n")
    assert re.search(r"<w:rPr>(?:(?!</w:rPr>).)*<w:shd[^>]*w:fill=\"F2F2F2\"", document, re.DOTALL)
    paragraph_section = re.search(r"<w:pPr>.*?</w:pPr>", document, re.DOTALL)
    if paragraph_section:
        assert "F2F2F2" not in paragraph_section.group(0)


def test_inline_code_shading_configurable(tmp_path: Path) -> None:
    config = BASE + '\n[code_block]\ninline_background = "DDEBF7"\n'
    document = _document_xml(tmp_path, "`code`\n", config)
    assert 'w:fill="DDEBF7"' in document


def test_inline_code_shading_can_be_disabled(tmp_path: Path) -> None:
    """``inline_background = ""`` 关闭底纹。"""
    config = BASE + '\n[code_block]\ninline_background = ""\n'
    document = _document_xml(tmp_path, "`code`\n", config)
    assert "F2F2F2" not in document


# ==========================================================================
# 四、[inline] 映射段
# ==========================================================================
def test_inline_defaults_to_same_name(tmp_path: Path) -> None:
    """不写 `[inline]` 时映射为同名——行为完全不变。"""
    config = _config(tmp_path, BASE)
    assert config.inline_mapping() == {
        "strong": "strong",
        "em": "em",
        "strike": "strike",
        "sup": "sup",
        "sub": "sub",
    }
    assert config.inline_style_name("sup") == "sup"


def test_inline_mapping_redirects(tmp_path: Path) -> None:
    config = _config(tmp_path, BASE + '\n[inline]\nsup = "sup_caret"\n')
    assert config.inline_style_name("sup") == "sup_caret"
    assert config.inline_style_name("strong") == "strong"  # 未映射的同名


def test_inline_mapping_affects_docx_rendering(tmp_path: Path) -> None:
    """``sup = "sup_caret"`` 时 ``^x^`` 应走 ``[styles.sup_caret]`` 的属性。"""
    config = BASE + (
        '\n[inline]\nsup = "sup_caret"\n'
        '\n[styles.sup_caret]\nfont.color = "AB1234"\nfont.size = "7pt"\n'
    )
    document = _document_xml(tmp_path, "E=mc^2^\n", config)
    assert 'w:val="AB1234"' in document
    assert 'w:val="14"' in document  # 7pt = 14 half-points
    assert 'w:val="superscript"' in document  # 语义仍然是上标


def test_inline_mapping_exposed_in_style_table(tmp_path: Path) -> None:
    """映射后的名字也要在样式表里可见（HTML 侧按名查表）。"""
    config = _config(
        tmp_path, BASE + '\n[inline]\nsup = "sup_caret"\n[styles.sup_caret]\ncolor = "#123"\n'
    )
    tree = build_style_tree(config)
    styles = tree["styles"]
    assert isinstance(styles, dict)
    assert "sup_caret" in styles
    assert styles["sup"] == styles["sup_caret"]  # 语义名作为别名


def test_inline_mapping_error_exposes_chain(tmp_path: Path) -> None:
    """需求：报错要**暴露映射链**——说明映射到谁、缺哪个 styles 段。"""
    config = _config(tmp_path, BASE + '\n[inline]\nsup = "sup_caret"\n')
    errors = validate_content(parse_dfm("E=mc^2^\n"), config)
    assert errors, "缺少 [styles.sup_caret] 应报错"
    message = errors[0].message
    assert errors[0].code == E_UNKNOWN_STYLE
    assert "sup_caret" in message
    assert "[inline].sup" in message
    assert "[styles.sup_caret]" in message


def test_inline_unmapped_semantic_reports_syntax(tmp_path: Path) -> None:
    """未映射但缺样式时，错误信息要指出是哪种语法用的。"""
    config = _config(tmp_path, BASE)
    # strong/em/strike 属于内置集合，不会报错；这里用显式引用一个不存在的自定义名
    errors = validate_content(parse_dfm("见 [x]{.nope}。\n"), config)
    assert errors
    assert "nope" in errors[0].message


def test_inline_mapping_passes_validation_when_declared(tmp_path: Path) -> None:
    config = _config(
        tmp_path, BASE + '\n[inline]\nsup = "sup_caret"\n[styles.sup_caret]\nfont.size = "8pt"\n'
    )
    assert validate_content(parse_dfm("E=mc^2^\n"), config) == []


def test_inline_mapping_does_not_change_ir(tmp_path: Path) -> None:
    """映射是**渲染/校验层**的事：IR 里仍然是语义名，解析器不碰 config。"""
    blocks = parse_dfm("**粗** E=mc^2^\n")
    assert isinstance(blocks[0], Paragraph)
    names = [node.style_name for node in blocks[0].content if isinstance(node, Styled)]
    assert names == ["strong", "sup"]
    assert blocks[0].content[0] == Styled(content=[Text("粗")], style_name="strong")


def test_inline_mapping_covers_all_semantic_names(tmp_path: Path) -> None:
    config = _config(
        tmp_path,
        BASE
        + '\n[inline]\nstrong = "b1"\nem = "i1"\nstrike = "s1"\nsup = "u1"\nsub = "d1"\n'
        + "\n[styles.b1]\n[styles.i1]\n[styles.s1]\n[styles.u1]\n[styles.d1]\n",
    )
    assert validate_content(parse_dfm("**a** *b* ~~c~~ ^d^ ~e~\n"), config) == []


def test_cell_inline_code_keeps_other_formatting(tmp_path: Path) -> None:
    """单元格里的代码底纹不应该把粗体挤掉（与公式无关，任何环境都跑）。"""
    document = _document_xml(tmp_path, "| 语法 | 值 |\n| --- | --- |\n| **粗** `code` | $x^2$ |\n")
    table = re.search(r"<w:tbl>.*?</w:tbl>", document, re.DOTALL)
    assert table is not None
    assert "<w:b/>" in table.group(0)
    assert "F2F2F2" in table.group(0)


@requires_xsl
def test_cell_inline_code_keeps_math(tmp_path: Path) -> None:
    """同一格里代码底纹与公式**共存**。

    公式只在有 ``MML2OMML.XSL`` 时才产出 OMML，所以这条单独拆出来并加跳过条件；
    底纹与粗体的断言留在上面那条（不依赖 XSL）。
    """
    document = _document_xml(tmp_path, "| 语法 | 值 |\n| --- | --- |\n| **粗** `code` | $x^2$ |\n")
    table = re.search(r"<w:tbl>.*?</w:tbl>", document, re.DOTALL)
    assert table is not None
    assert "oMath" in table.group(0)
    assert "F2F2F2" in table.group(0)


def test_code_inline_ir_node_still_plain() -> None:
    table = parse_dfm("| a |\n| --- |\n| `x` |\n")[0]
    assert isinstance(table, Table)
    assert table.cell_nodes[1][0] == [Code("x")]


def test_style_table_unchanged_without_inline_section(tmp_path: Path) -> None:
    """没有 `[inline]` 时样式表内容与以前一致（只多别名逻辑且无重定向）。"""
    config = _config(tmp_path, BASE + "\n[styles.strong]\nfont.bold = true\n")
    table = build_style_table(config)
    assert table["strong"] == {"font": {"bold": True}}

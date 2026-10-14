"""诊断契约（第 3 周）：未闭合标记 E3001、未知语言 E2001、语法错误 E4001。

设计取舍：**解析器保持宽容**（未闭合标记退化为字面文本、内容不丢），
诊断由 ``check`` 基于**规范化后的源文本 + IR** 给出，所以：

- ``build`` 永远能产出结果（渲染字面文本），不会被诊断挡住；
- ``check`` / ``check --strict`` 负责把问题报出来，并给出 ``file:line:col:code:message``。
"""

from pathlib import Path

from docgen import errors
from docgen.config import Config, load_config
from docgen.diagnostics import (
    DEFAULT_LANGUAGES,
    SOURCE_ERROR_KINDS,
    format_content_error,
    scan_diagnostics,
    scan_source,
    with_diagnostics,
)
from docgen.parser.dfm import parse_dfm
from docgen.validate import validate_content

CONFIG = """\
config_version = "0.1"

[styles.caption]
color = "#666"

[code_block]
background = "#f5f5f5"
"""


def _config(tmp_path: Path) -> Config:
    path = tmp_path / "config.toml"
    path.write_text(CONFIG, encoding="utf-8")
    return load_config(path)


# --------------------------------------------------------------------------
# scan_source：只依赖源文本
# --------------------------------------------------------------------------
def test_clean_source_has_no_diagnostics() -> None:
    text = "# 标题\n\n[[img:a.png]] 与 [x]{.caption} 和 $x^2$\n\n```python\nprint(1)\n```\n"
    assert scan_source(text, SOURCE_ERROR_KINDS) == []


def test_unclosed_image_marker() -> None:
    found = scan_source("第一行\n\n[[img:pics/a.png\n", SOURCE_ERROR_KINDS)
    assert [err.code for err in found] == [errors.E_UNCLOSED_MARKER]
    assert found[0].line == 3
    assert found[0].col == 1


def test_unclosed_pagebreak_marker() -> None:
    found = scan_source("[[pageb", SOURCE_ERROR_KINDS)
    assert [err.code for err in found] == [errors.E_UNCLOSED_MARKER]


def test_unclosed_style_attribute() -> None:
    found = scan_source("文字 [关键字]{.caption\n", SOURCE_ERROR_KINDS)
    assert [err.code for err in found] == [errors.E_UNCLOSED_MARKER]


def test_style_attribute_with_empty_name() -> None:
    found = scan_source("[关键字]{}\n", SOURCE_ERROR_KINDS)
    assert [err.code for err in found] == [errors.E_UNCLOSED_MARKER]


def test_unclosed_inline_math() -> None:
    found = scan_source("公式 $x^2 没闭合\n", SOURCE_ERROR_KINDS)
    assert [err.code for err in found] == [errors.E_UNCLOSED_MARKER]


def test_unclosed_block_math() -> None:
    found = scan_source("$$\nE = mc^2\n", SOURCE_ERROR_KINDS)
    assert [err.code for err in found] == [errors.E_UNCLOSED_MARKER]


def test_single_dollar_amount_is_not_math() -> None:
    assert scan_source("$100\n", SOURCE_ERROR_KINDS) == []


def test_escaped_marker_is_not_reported() -> None:
    assert scan_source("\\[关键字]{.caption\n", SOURCE_ERROR_KINDS) == []


def test_wiki_marker_inside_code_fence_is_ignored() -> None:
    text = "```\n[[img:a.png\n```\n"
    assert scan_source(text, SOURCE_ERROR_KINDS) == []


def test_wiki_marker_inside_inline_code_is_ignored() -> None:
    assert scan_source("`[[img:a.png`\n", SOURCE_ERROR_KINDS) == []


def test_unbalanced_fence_is_syntax_error() -> None:
    found = scan_source("```python\nprint(1)\n", SOURCE_ERROR_KINDS)
    assert [err.code for err in found] == [errors.E_SYNTAX]
    assert found[0].line == 1
    assert "```" in found[0].message


def test_balanced_fences_are_fine() -> None:
    assert scan_source("```\na\n```\n\n~~~\nb\n~~~\n", SOURCE_ERROR_KINDS) == []


def test_column_points_at_the_marker() -> None:
    found = scan_source("前缀 [[img:a\n", SOURCE_ERROR_KINDS)
    assert found[0].col == 4


# --------------------------------------------------------------------------
# scan_diagnostics：源文本 + IR（未知语言需要 IR）
# --------------------------------------------------------------------------
def test_unknown_language_is_reported() -> None:
    text = "```cobol\nDISPLAY 'HI'.\n```\n"
    found = scan_diagnostics(text, parse_dfm(text))
    assert [err.code for err in found] == [errors.E_UNKNOWN_LANGUAGE]
    assert found[0].line == 1
    assert "cobol" in found[0].message


def test_unknown_language_inside_list_item_is_reported() -> None:
    text = "- 项\n\n  ```cobol\n  DISPLAY 'HI'.\n  ```\n"
    found = scan_diagnostics(text, parse_dfm(text))
    assert [err.code for err in found] == [errors.E_UNKNOWN_LANGUAGE]


def test_known_languages_pass() -> None:
    for language in ("python", "markdown", "bash", "json", "yaml", "text", ""):
        text = f"```{language}\ncode\n```\n"
        assert scan_diagnostics(text, parse_dfm(text)) == []


def test_language_matching_is_case_insensitive_and_aliased() -> None:
    for language in ("Python", "PY", "js", "ts", "sh"):
        text = f"```{language}\ncode\n```\n"
        assert scan_diagnostics(text, parse_dfm(text)) == [], language


def test_language_list_is_documented_shape() -> None:
    assert {"python", "markdown", "bash", "json", "yaml", "text"} <= DEFAULT_LANGUAGES


# --------------------------------------------------------------------------
# with_diagnostics：与 validate_content 合并
# --------------------------------------------------------------------------
def test_with_diagnostics_merges_validation_and_diagnostics(tmp_path: Path) -> None:
    config = _config(tmp_path)
    text = "[x]{.nope}\n\n[[img:a.png\n"
    blocks = parse_dfm(text)
    merged = with_diagnostics(text, blocks, config)
    assert [err.code for err in merged] == [errors.E_UNKNOWN_STYLE, errors.E_UNCLOSED_MARKER]


def test_validate_only_ignores_unclosed_markers(tmp_path: Path) -> None:
    """不开启诊断时，check 仍只报语义错误（保持向后兼容）。"""
    config = _config(tmp_path)
    blocks = parse_dfm("[[img:a.png\n")
    assert validate_content(blocks, config) == []


def test_balanced_multiline_block_math_is_not_reported() -> None:
    """跨行块级公式是合法的：``$$`` 成对出现在两行上。"""
    text = "行内 $x^2$ 正常\n\n$$\nE = mc^2\n$$\n\n结尾 [[img:a.png]] 正常\n"
    assert scan_source(text, SOURCE_ERROR_KINDS) == []


def test_clean_full_fixture_has_no_diagnostics(tmp_path: Path) -> None:
    """真实夹具跑严格诊断必须干净（覆盖所有节点类型）。"""
    from pathlib import Path as _Path

    fixtures = _Path(__file__).parent / "fixtures"
    text = (fixtures / "full.md").read_text(encoding="utf-8")
    config = load_config(fixtures / "minimal.toml")
    assert with_diagnostics(text, parse_dfm(text), config, base_dir=fixtures) == []


def test_format_content_error_is_file_line_col_shape(tmp_path: Path) -> None:
    found = scan_source("[[img:a\n", SOURCE_ERROR_KINDS)
    assert format_content_error(found[0], str(tmp_path / "doc.md")) == (
        f"{tmp_path / 'doc.md'}:1:1:E3001:未闭合的标记: [["
    )

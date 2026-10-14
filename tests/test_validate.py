"""语义校验契约：样式引用与图片路径（第 2 周）。"""

from pathlib import Path

from docgen import errors
from docgen.config import Config, load_config
from docgen.parser.dfm import parse_dfm
from docgen.validate import validate_content

CONFIG = """\
config_version = "0.1"

[document]
font_size = "16px"

[styles.keyword]
color = "#0000FF"

[code_block]
background = "#f5f5f5"
"""


def _config(tmp_path: Path) -> Config:
    path = tmp_path / "config.toml"
    path.write_text(CONFIG, encoding="utf-8")
    return load_config(path)


def test_valid_document_has_no_errors(tmp_path: Path) -> None:
    (tmp_path / "pics").mkdir()
    (tmp_path / "pics" / "a.png").write_bytes(b"png")
    config = _config(tmp_path)
    blocks = parse_dfm("[关键字]{.keyword} 与 ![图](pics/a.png)\n")
    assert validate_content(blocks, config, base_dir=tmp_path) == []


def test_unknown_style_is_reported_with_line(tmp_path: Path) -> None:
    config = _config(tmp_path)
    blocks = parse_dfm("第一行\n\n[x]{.nope}\n")
    found = validate_content(blocks, config, source=tmp_path / "doc.md")
    assert len(found) == 1
    assert found[0].code == errors.E_UNKNOWN_STYLE
    assert found[0].line == 3
    assert "nope" in found[0].message
    assert str(found[0]).startswith(f"{tmp_path / 'doc.md'}:3:0:E1003:")


def test_style_reference_inside_nested_blocks_is_found(tmp_path: Path) -> None:
    config = _config(tmp_path)
    blocks = parse_dfm("- 项 [x]{.missing}\n\n> [y]{.gone}\n")
    found = validate_content(blocks, config)
    assert [err.code for err in found] == [errors.E_UNKNOWN_STYLE, errors.E_UNKNOWN_STYLE]
    assert {err.line for err in found} == {1, 3}


def test_markdown_emphasis_styles_are_builtin(tmp_path: Path) -> None:
    """**粗体** 走的是内置样式名，不应该被报成未知样式。"""
    config = _config(tmp_path)
    blocks = parse_dfm("**粗** *斜* ~~删~~ `code`\n")
    assert validate_content(blocks, config) == []


def test_missing_image_is_reported(tmp_path: Path) -> None:
    config = _config(tmp_path)
    blocks = parse_dfm("[[img:pics/gone.png]]\n")
    found = validate_content(blocks, config, source=tmp_path / "doc.md")
    assert len(found) == 1
    assert found[0].code == errors.E_CONFIG
    assert found[0].line == 1
    assert "gone.png" in found[0].message


def test_existing_image_passes(tmp_path: Path) -> None:
    (tmp_path / "pics").mkdir()
    (tmp_path / "pics" / "a.png").write_bytes(b"png")
    config = _config(tmp_path)
    blocks = parse_dfm("[[img:pics/a.png]]\n\n![alt](pics/a.png)\n")
    assert validate_content(blocks, config, base_dir=tmp_path) == []


def test_remote_image_is_not_checked(tmp_path: Path) -> None:
    config = _config(tmp_path)
    blocks = parse_dfm("![alt](https://example.com/a.png)\n")
    assert validate_content(blocks, config) == []


def test_code_block_language_style_is_known(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text(CONFIG + '\n[code_block.python]\ncolor = "#222"\n', encoding="utf-8")
    config = load_config(path)
    blocks = parse_dfm("[x]{.python}\n")
    assert validate_content(blocks, config) == []


def test_error_as_dict_shape(tmp_path: Path) -> None:
    config = _config(tmp_path)
    found = validate_content(parse_dfm("[x]{.nope}\n"), config, source=Path("input.md"))
    assert found[0].as_dict() == {
        "file": "input.md",
        "line": 1,
        "col": 0,
        "code": "E1003",
        "message": "引用了不存在的样式: nope",
    }

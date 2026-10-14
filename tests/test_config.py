"""config 契约（手册 §5.3 / 第 2 周）：TOML 加载、include、based_on、@ref、for=false。

错误码：E5001 配置缺失/版本不符/非法值，E1001 循环继承，E1002 继承深度超限，E1003 引用不存在。
"""

from pathlib import Path

import pytest

from docgen import errors
from docgen.config import build_style_table, load_config

BASE_CONFIG = """\
config_version = "0.1"

[document]
font_family = "sans-serif"
font_size = "16px"
line_height = "1.6"

[styles.heading1]
font_size = "2em"
font_weight = "bold"
color = "#111"

[styles.heading2]
based_on = "heading1"
font_size = "1.5em"

[styles.body]
font_size = "@document.font_size"
color = "#333"

[styles.keyword]
color = "#0000FF"
font_weight = "bold"

[styles.keyword_return]
based_on = "keyword"
color = "#FF0000"

[code_block]
background = "#f5f5f5"
font_family = "monospace"

[code_block.python]
based_on = "code_block"
color = "#222"
"""


def _write(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def base_config(tmp_path: Path) -> Path:
    return _write(tmp_path, "config.toml", BASE_CONFIG)


# --------------------------------------------------------------------------
# 加载与版本
# --------------------------------------------------------------------------
def test_load_minimal_config(base_config: Path) -> None:
    config = load_config(base_config)
    assert config.version == "0.1"
    assert config.document["font_family"] == "sans-serif"
    assert set(config.styles) >= {"heading1", "heading2", "body", "keyword", "keyword_return"}
    assert config.styles["heading1"].properties["font_weight"] == "bold"
    assert config.styles["heading2"].based_on == "heading1"


def test_missing_config_file(tmp_path: Path) -> None:
    with pytest.raises(errors.DocGenError) as caught:
        load_config(tmp_path / "nope.toml")
    assert caught.value.code == errors.E_CONFIG


def test_missing_version_is_config_error(tmp_path: Path) -> None:
    path = _write(tmp_path, "config.toml", '[styles.a]\ncolor = "red"\n')
    with pytest.raises(errors.DocGenError) as caught:
        load_config(path)
    assert caught.value.code == errors.E_CONFIG
    assert "config_version" in caught.value.message


def test_wrong_version_is_config_error(tmp_path: Path) -> None:
    path = _write(tmp_path, "config.toml", 'config_version = "9.9"\n')
    with pytest.raises(errors.DocGenError) as caught:
        load_config(path)
    assert caught.value.code == errors.E_CONFIG


def test_invalid_toml_is_config_error(tmp_path: Path) -> None:
    path = _write(tmp_path, "config.toml", 'config_version = "0.1"\n[styles.a\n')
    with pytest.raises(errors.DocGenError) as caught:
        load_config(path)
    assert caught.value.code == errors.E_CONFIG


def test_non_utf8_config_is_config_error(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_bytes(b'config_version = "\xff"\n')
    with pytest.raises(errors.DocGenError) as caught:
        load_config(path)
    assert caught.value.code == errors.E_CONFIG


def test_reserved_keys_are_not_styles(base_config: Path) -> None:
    config = load_config(base_config)
    assert "config_version" not in config.styles
    assert "include" not in config.styles
    assert config.code_block["background"] == "#f5f5f5"
    assert config.code_blocks["python"]["based_on"] == "code_block"


# --------------------------------------------------------------------------
# include
# --------------------------------------------------------------------------
def test_include_merges_and_later_wins(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "base.toml",
        'config_version = "0.1"\n\n[document]\nfont_size = "14px"\ncolor = "#aaa"\n\n'
        '[styles.body]\ncolor = "#111"\n',
    )
    main = _write(
        tmp_path,
        "config.toml",
        'config_version = "0.1"\ninclude = ["base.toml"]\n\n'
        '[document]\nfont_size = "16px"\n\n[styles.body]\nfont_size = "1em"\n',
    )
    config = load_config(main)
    # 自身覆盖 include
    assert config.document["font_size"] == "16px"
    # include 里独有的键保留
    assert config.document["color"] == "#aaa"
    # 样式浅合并：include 的 color 与自身的 font_size 都在
    assert config.styles["body"].properties == {"color": "#111", "font_size": "1em"}


def test_multiple_includes_later_overrides_earlier(tmp_path: Path) -> None:
    _write(tmp_path, "a.toml", 'config_version = "0.1"\n\n[document]\nfont_size = "10px"\n')
    _write(tmp_path, "b.toml", 'config_version = "0.1"\n\n[document]\nfont_size = "12px"\n')
    main = _write(
        tmp_path,
        "config.toml",
        'config_version = "0.1"\ninclude = ["a.toml", "b.toml"]\n',
    )
    assert load_config(main).document["font_size"] == "12px"


def test_recursive_include_cycle_is_config_error(tmp_path: Path) -> None:
    _write(tmp_path, "a.toml", 'config_version = "0.1"\ninclude = ["b.toml"]\n')
    b = _write(tmp_path, "b.toml", 'config_version = "0.1"\ninclude = ["a.toml"]\n')
    with pytest.raises(errors.DocGenError) as caught:
        load_config(b)
    assert caught.value.code == errors.E_CONFIG
    assert "include" in caught.value.message


def test_missing_include_is_config_error(tmp_path: Path) -> None:
    main = _write(tmp_path, "config.toml", 'config_version = "0.1"\ninclude = ["nope.toml"]\n')
    with pytest.raises(errors.DocGenError) as caught:
        load_config(main)
    assert caught.value.code == errors.E_CONFIG


# --------------------------------------------------------------------------
# based_on 继承
# --------------------------------------------------------------------------
def test_single_level_inheritance(base_config: Path) -> None:
    table = build_style_table(load_config(base_config))
    assert table["heading2"] == {
        "font_size": "1.5em",
        "font_weight": "bold",
        "color": "#111",
    }


def test_multi_level_inheritance(base_config: Path) -> None:
    table = build_style_table(load_config(base_config))
    assert table["keyword_return"]["color"] == "#FF0000"  # 子覆盖父
    assert table["keyword_return"]["font_weight"] == "bold"  # 继承父


def test_style_without_based_on_is_itself(base_config: Path) -> None:
    table = build_style_table(load_config(base_config))
    assert table["keyword"] == {"color": "#0000FF", "font_weight": "bold"}


def test_code_block_inheritance(base_config: Path) -> None:
    table = build_style_table(load_config(base_config))
    assert table["python"] == {"background": "#f5f5f5", "font_family": "monospace", "color": "#222"}


def test_cycles_are_detected(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "config.toml",
        'config_version = "0.1"\n\n[styles.a]\nbased_on = "b"\n\n[styles.b]\nbased_on = "a"\n',
    )
    with pytest.raises(errors.DocGenError) as caught:
        build_style_table(load_config(path))
    assert caught.value.code == errors.E_CIRCULAR_INHERITANCE


def test_self_inheritance_is_a_cycle(tmp_path: Path) -> None:
    path = _write(tmp_path, "config.toml", 'config_version = "0.1"\n\n[styles.a]\nbased_on = "a"\n')
    with pytest.raises(errors.DocGenError) as caught:
        build_style_table(load_config(path))
    assert caught.value.code == errors.E_CIRCULAR_INHERITANCE


def test_unknown_parent_is_config_error(tmp_path: Path) -> None:
    path = _write(
        tmp_path, "config.toml", 'config_version = "0.1"\n\n[styles.a]\nbased_on = "nope"\n'
    )
    with pytest.raises(errors.DocGenError) as caught:
        build_style_table(load_config(path))
    assert caught.value.code == errors.E_CONFIG


def _chain(length: int) -> str:
    lines = ['config_version = "0.1"', "", "[styles.s1]", 'color = "red"', ""]
    for level in range(2, length + 1):
        lines += [f"[styles.s{level}]", f'based_on = "s{level - 1}"', ""]
    return "\n".join(lines)


def test_depth_limit_allows_eight_levels(tmp_path: Path) -> None:
    path = _write(tmp_path, "config.toml", _chain(8))
    assert build_style_table(load_config(path))["s8"]["color"] == "red"


def test_depth_limit_rejects_nine_levels(tmp_path: Path) -> None:
    path = _write(tmp_path, "config.toml", _chain(9))
    with pytest.raises(errors.DocGenError) as caught:
        build_style_table(load_config(path))
    assert caught.value.code == errors.E_INHERITANCE_DEPTH


# --------------------------------------------------------------------------
# @ref 与 for = false
# --------------------------------------------------------------------------
def test_ref_resolves_to_document_value(base_config: Path) -> None:
    table = build_style_table(load_config(base_config))
    assert table["body"]["font_size"] == "16px"
    assert table["body"]["color"] == "#333"


def test_ref_to_style_key(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "config.toml",
        'config_version = "0.1"\n\n[styles.base]\ncolor = "#abc"\n\n'
        '[styles.use]\ncolor = "@styles.base.color"\n',
    )
    assert build_style_table(load_config(path))["use"]["color"] == "#abc"


def test_chained_ref_is_resolved_recursively(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "config.toml",
        'config_version = "0.1"\n\n[document]\nfont_size = "15px"\n\n'
        '[styles.a]\nfont_size = "@document.font_size"\n\n'
        '[styles.b]\nfont_size = "@styles.a.font_size"\n',
    )
    assert build_style_table(load_config(path))["b"]["font_size"] == "15px"


def test_unknown_ref_is_unknown_style_error(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "config.toml",
        'config_version = "0.1"\n\n[styles.a]\nfont_size = "@document.nope"\n',
    )
    with pytest.raises(errors.DocGenError) as caught:
        build_style_table(load_config(path))
    assert caught.value.code == errors.E_UNKNOWN_STYLE


def test_soft_delete_removes_inherited_value(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "config.toml",
        'config_version = "0.1"\n\n[styles.base]\ncolor = "red"\nfont_weight = "bold"\n\n'
        '[styles.child]\nbased_on = "base"\ncolor = false\n',
    )
    assert build_style_table(load_config(path))["child"] == {"font_weight": "bold"}


def test_style_objects_keep_name_and_parent(base_config: Path) -> None:
    config = load_config(base_config)
    assert config.styles["heading2"].name == "heading2"
    assert config.styles["body"].based_on is None

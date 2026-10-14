"""错误码契约（手册 §11）：格式 ``file:line:col:code:message``，无 file 时 ``code:message``。"""

import pytest

from docgen import errors


def test_error_code_constants() -> None:
    assert errors.E_CIRCULAR_INHERITANCE == "E1001"
    assert errors.E_INHERITANCE_DEPTH == "E1002"
    assert errors.E_UNKNOWN_STYLE == "E1003"
    assert errors.E_UNKNOWN_LANGUAGE == "E2001"
    assert errors.E_UNCLOSED_MARKER == "E3001"
    assert errors.E_SYNTAX == "E4001"
    assert errors.E_CONFIG == "E5001"


def test_all_error_codes_are_unique_and_well_formed() -> None:
    codes = [value for name, value in vars(errors).items() if name.startswith("E_")]
    assert len(codes) == len(set(codes)) == 7
    assert all(len(code) == 5 and code[0] == "E" and code[1:].isdigit() for code in codes)


def test_str_without_file_is_code_and_message() -> None:
    err = errors.DocGenError(errors.E_UNKNOWN_STYLE, "引用了不存在的样式")
    assert str(err) == "E1003:引用了不存在的样式"
    assert err.args == ("E1003:引用了不存在的样式",)


def test_str_with_file_is_file_line_col_code_message() -> None:
    err = errors.DocGenError(
        errors.E_UNCLOSED_MARKER,
        "未闭合的标记",
        file="input.md",
        line=12,
        col=3,
    )
    assert str(err) == "input.md:12:3:E3001:未闭合的标记"


def test_error_is_raisable_and_catchable() -> None:
    with pytest.raises(errors.DocGenError) as caught:
        raise errors.DocGenError(errors.E_CONFIG, "config 版本不符")
    assert caught.value.code == "E5001"

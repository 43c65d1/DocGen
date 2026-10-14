"""输入规范化的行为契约：去 BOM + 统一换行为 LF。"""

import itertools

from docgen.normalize import normalize_text

ENDINGS = ("\r\n", "\r", "\n")
LINE_BODIES = ("# 标题", "正文段落", "code  `x`", " 缩进")


def test_removes_leading_bom() -> None:
    assert normalize_text("\ufeff# 标题\n") == "# 标题\n"


def test_bom_in_the_middle_is_content() -> None:
    assert normalize_text("a\ufeffb") == "a\ufeffb"


def test_windows_line_endings() -> None:
    assert normalize_text("a\r\nb\r\n") == "a\nb\n"


def test_old_mac_line_endings() -> None:
    assert normalize_text("a\rb\r") == "a\nb\n"


def test_mixed_line_endings() -> None:
    assert normalize_text("a\r\nb\rc\nd") == "a\nb\nc\nd"


def test_mixed_line_endings_are_idempotent() -> None:
    once = normalize_text("\ufeffa\r\nb\rc")
    assert normalize_text(once) == once == "a\nb\nc"


def test_every_ending_combination_normalizes_to_lf() -> None:
    """穷举 3 种换行的所有组合：规范化输出只与行内容有关。"""
    cases = 0
    for count in (1, 2, 3, 4):
        for endings in itertools.product(ENDINGS, repeat=count):
            lines = list(LINE_BODIES[:count])
            raw = "".join(body + ending for body, ending in zip(lines, endings))
            assert normalize_text(raw) == "\n".join(lines) + "\n"
            cases += 1
    assert cases == 3 + 9 + 27 + 81


def test_leaves_text_without_line_endings_alone() -> None:
    assert normalize_text("单行内容") == "单行内容"

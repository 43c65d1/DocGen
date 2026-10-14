"""单位换算（完整版手册 §17.1）。

OOXML 用物理单位：字号半点（half-point）、行距倍数、段前后行数、缩进字符数。
config 里允许写 ``12pt`` / ``16px`` / ``1.5em`` / ``1.5``，统一在这里换算，
避免每个渲染模块各写一套。
"""

from __future__ import annotations

from typing import Any

__all__ = ["to_points"]

#: em / rem 的换算基准（正文 12pt）
BASE_POINTS = 12.0
#: px -> pt 的换算（96 DPI 屏幕像素）
PX_TO_POINTS = 0.75


def to_points(value: Any, base: float = BASE_POINTS) -> Any:
    """把 config 里的长度值换算成 ``docx.shared.Pt``（无后缀数字按磅计）。"""
    from docx.shared import Pt

    if isinstance(value, (int, float)):
        return Pt(float(value))
    text = str(value).strip().lower()
    for suffix in ("pt", "px", "em", "rem"):
        if text.endswith(suffix):
            number = float(text[: -len(suffix)])
            if suffix in ("em", "rem"):
                return Pt(number * base)
            if suffix == "px":
                return Pt(number * PX_TO_POINTS)
            return Pt(number)
    return Pt(float(text))

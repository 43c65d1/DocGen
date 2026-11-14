"""单位换算。

OOXML 用物理单位：字号半点（half-point）、行距倍数、段前后行数、缩进字符数。
config 里允许写 ``12pt`` / ``16px`` / ``1.5em`` / ``小四`` / ``三号``，统一在这里换算，
避免每个渲染模块各写一套。
"""

from __future__ import annotations

from typing import Any

from .errors import E_CONFIG, DocGenError

__all__ = ["CN_FONT_SIZES", "to_points"]

#: em / rem 的换算基准（正文 12pt）
BASE_POINTS = 12.0
#: px -> pt 的换算（96 DPI 屏幕像素）
PX_TO_POINTS = 0.75

#: 中文字号（号数制）-> 磅值。
#:
#: Word / WPS 采用同一套换算（也是高校论文规范里「三号」「小四」的实际含义）：
#: 值越小号越大；「小 X 号」比「X 号」小一档。这里采用软件口径（pt），
#: 严格印刷标准的号数按毫米定义，与 pt 换算差异 <1%，文档排版可忽略。
CN_FONT_SIZES: dict[str, float] = {
    "初号": 42.0,
    "小初": 36.0,
    "一号": 26.0,
    "小一": 24.0,
    "二号": 22.0,
    "小二": 18.0,
    "三号": 16.0,
    "小三": 15.0,
    "四号": 14.0,
    "小四": 12.0,
    "五号": 10.5,
    "小五": 9.0,
    "六号": 7.5,
    "小六": 6.5,
    "七号": 5.5,
    "八号": 5.0,
}


def to_points(value: Any, base: float = BASE_POINTS) -> Any:
    """把 config 里的长度值换算成 ``docx.shared.Pt``。

    支持：无后缀数字（按磅）、``pt`` / ``磅`` / ``px`` / ``em`` / ``rem``、
    中文字号（``初号`` / ``小四`` / ``三号`` …，可带「号」后缀）。
    无法识别时报 ``E5001``（不再抛 ValueError）。
    """
    from docx.shared import Pt

    if isinstance(value, bool):  # bool 是 int 子类，单独拒绝
        raise DocGenError(E_CONFIG, f"字号不能是布尔值: {value!r}")
    if isinstance(value, (int, float)):
        return Pt(float(value))
    raw = str(value).strip()
    # 中文字号：允许「小四」「小四号」「三号」等写法
    keyword = raw[:-1] if raw.endswith(("号", "號")) else raw
    for candidate in (raw, keyword):
        if candidate in CN_FONT_SIZES:
            return Pt(CN_FONT_SIZES[candidate])
    text = raw.lower()
    for suffix in ("pt", "px", "磅", "em", "rem"):
        if not text.endswith(suffix):
            continue
        try:
            number = float(text[: -len(suffix)].strip())
        except ValueError:
            break
        if suffix in ("em", "rem"):
            return Pt(number * base)
        if suffix == "px":
            return Pt(number * PX_TO_POINTS)
        return Pt(number)
    try:
        return Pt(float(text))
    except ValueError:
        raise DocGenError(
            E_CONFIG,
            f"字号无法识别: {value!r}（支持 12pt / 1.5em / 16px / 小四 / 三号 等）",
        ) from None

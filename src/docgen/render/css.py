"""从 config 生成 CSS（手册 §4 / 第 4 周）。

- ``render_css(config)``：把展开后的样式表映射成类选择器规则
  （``[styles.heading1]`` -> ``h1``、``[styles.caption]`` -> ``.caption``…）。
- 正文排版只使用 ``[document]`` 里的值，未声明的用最小的可读默认值。

渲染层只认 config + IR：这里不解析 DFM，也不直接读文件。
"""

from __future__ import annotations

from typing import Any

from ..config import Config, build_style_tree

__all__ = ["STYLE_SELECTORS", "render_css"]

#: 样式名 -> CSS 选择器（值用 ``{}`` 占位，供 ``.format`` 替换）
STYLE_SELECTORS: dict[str, str] = {
    "heading1": "h1",
    "heading2": "h2",
    "heading3": "h3",
    "heading4": "h4",
    "heading5": "h5",
    "heading6": "h6",
    "body": "p",
    "paragraph": "p",
    "strong": "strong",
    "em": "em",
    "strike": "del",
    "code": "code",
    "caption": ".caption",
    "keyword": ".keyword",
}

#: 样式属性 -> CSS 属性（同名直传的除外）
PROPERTY_ALIASES: dict[str, str] = {
    "background": "background-color",
    "line_height": "line-height",
    "font_family": "font-family",
    "font_size": "font-size",
    "font_weight": "font-weight",
    "font_style": "font-style",
    "text_align": "text-align",
    "text_indent": "text-indent",
    "margin_top": "margin-top",
    "margin_bottom": "margin-bottom",
    "padding_left": "padding-left",
    "border_radius": "border-radius",
}

_PASSTHROUGH = frozenset(
    {"color", "background-color", "border", "border-left", "border-radius", "width", "height"}
)

#: 未在 config 中声明时的正文默认值（保持输出可读、可打印）
_BODY_DEFAULTS: dict[str, str] = {
    "font-family": "sans-serif",
    "font-size": "16px",
    "line-height": "1.6",
    "color": "#222",
}


def property_to_css(name: str) -> str:
    """样式属性名 -> CSS 属性名（``font_size`` -> ``font-size``）。"""
    if name in PROPERTY_ALIASES:
        return PROPERTY_ALIASES[name]
    if name in _PASSTHROUGH:
        return name
    return name.replace("_", "-")


def declarations(properties: dict[str, Any]) -> list[tuple[str, str]]:
    """把样式属性转成有序的 CSS 声明（跳过空值、内部键与 Word 专用的嵌套表）。

    ``font`` / ``font.*`` 是 **Word 口径**的嵌套属性（``font.bold`` 展开成
    ``{"font": {"bold": true}}``）；CSS 对应物是 ``font-weight`` / ``font-style`` 这类
    扁平键。嵌套表直接转字符串会产出 ``font: {'bold': True}`` 这种废声明（实测踩到），
    所以这里整段跳过——想要 HTML 生效就在 config 里同时写扁平键。
    """
    result: list[tuple[str, str]] = []
    for key in sorted(properties):
        if key == "based_on" or key == "font" or key.startswith("font."):
            continue
        value = properties[key]
        if value is None or value is False or value == "":
            continue
        if isinstance(value, dict):
            continue  # 其它嵌套命名空间（如 table/image）也不属于 CSS
        result.append((property_to_css(key), _css_value(value)))
    return result


def inline_style(properties: dict[str, Any]) -> str:
    """``style="..."`` 的值；没有声明时返回空串。"""
    return "; ".join(f"{name}: {value}" for name, value in declarations(properties))


def _css_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def render_css(config: Config) -> str:
    """生成完整 ``<style>`` 内容（确定性：选择器与属性都排序）。"""
    tree = build_style_tree(config)
    styles = tree.get("styles", {})
    assert isinstance(styles, dict)

    # 默认值先铺底，config 的同名属性覆盖它（按 CSS 属性名去重，避免重复声明）
    body_properties: dict[str, Any] = {
        **{property_to_css(k): v for k, v in _BODY_DEFAULTS.items()},
        **{property_to_css(k): v for k, v in config.document.items()},
    }

    lines = ["/* 由 docgen 从 config 生成 */", "body {"]
    for name, value in sorted(body_properties.items()):
        lines.append(f"  {name}: {_css_value(value)};")
    lines.append("}")
    lines.append("")

    for style_name in sorted(styles):
        properties = styles[style_name]
        if not isinstance(properties, dict) or not properties:
            continue
        selector = STYLE_SELECTORS.get(style_name)
        if selector is None:
            continue
        body = declarations(properties)
        if not body:
            continue
        lines.append(f"{selector} {{")
        for name, value in body:
            lines.append(f"  {name}: {value};")
        lines.append("}")
        lines.append("")

    lines.extend(
        [
            "pre {",
            "  background: #f5f5f5;",
            "  padding: 0.75em;",
            "  overflow-x: auto;",
            "}",
            "",
            "table {",
            "  border-collapse: collapse;",
            "}",
            "",
            "th, td {",
            "  border: 1px solid #ccc;",
            "  padding: 0.35em 0.6em;",
            "}",
            "",
            "blockquote {",
            "  margin-left: 0;",
            "  padding-left: 1em;",
            "  border-left: 3px solid #ddd;",
            "  color: #555;",
            "}",
            "",
            "hr.pagebreak {",
            "  border: 0;",
            "  border-top: 1px dashed #999;",
            "  margin: 1.5em 0;",
            "}",
        ]
    )
    return "\n".join(lines) + "\n"

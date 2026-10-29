"""DFM 自研标记的行内规则。

这些规则注册在 markdown-it-py 内置行内规则之前（``before="escape"``），
因为它们必须看到**原始**源文本：

- ``[[img:path]]`` / ``[[pagebreak]]``
- ``[文字]{.样式名}``
- 行内数学 ``$latex$`` 与块级数学 ``$$ ... $$``
- ``\\`` 转义由 markdown-it 的 escape 规则处理，无需自定义
  （数学内容在自定义规则里直接切片，因此 ``\\,`` 不会被当成转义吃掉）

冲突规则（手册 5.1）：数学内不解析 Markdown；``[...]{...}`` 内不解析嵌套 ``[...]``；
转义只作用于后一个字符。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from markdown_it.token import Token

if TYPE_CHECKING:  # pragma: no cover
    from markdown_it import MarkdownIt
    from markdown_it.rules_inline import StateInline


def rule_wiki(state: StateInline, silent: bool) -> bool:
    """``[[...]]``：白名单为 ``[[img:path]]``、``[[pagebreak]]``、``[[toc]]``、``[[ref:目标]]``。"""
    src = state.src
    if src[state.pos : state.pos + 2] != "[[":
        return False

    end = src.find("]]", state.pos + 2)
    if end == -1:
        return False

    inner = src[state.pos + 2 : end]
    keywords = ("pagebreak", "toc", "sectionbreak")
    if inner not in keywords and not inner.startswith(("img:", "ref:", "fn:")):
        return False

    if silent:
        return True

    if inner == "pagebreak":
        token = Token("dfm_pagebreak", "", 0)
    elif inner == "toc":
        token = Token("dfm_toc", "", 0)
    elif inner == "sectionbreak":
        token = Token("dfm_sectionbreak", "", 0)
    elif inner.startswith("ref:"):
        token = Token("dfm_ref", "", 0)
        token.content = inner[len("ref:") :]
    elif inner.startswith("fn:"):
        token = Token("dfm_footnote", "", 0)
        token.content = inner[len("fn:") :]
    else:
        token = Token("dfm_image", "", 0)
        token.content = inner[len("img:") :]
    state.pushPending()
    state.tokens.append(token)
    state.pos = end + 2
    return True


def rule_styled(state: StateInline, silent: bool) -> bool:
    """``[文字]{.样式名}``：属性语法内不解析嵌套 ``[...]``。"""
    src = state.src
    if src[state.pos] != "[" or src[state.pos : state.pos + 2] == "[[":
        return False

    close = src.find("]", state.pos + 1)
    if close == -1 or src[close + 1 : close + 2] != "{":
        return False

    brace_end = src.find("}", close + 2)
    if brace_end == -1:
        return False

    label = src[state.pos + 1 : close]
    if "[" in label:
        return False

    style_name = src[close + 2 : brace_end].strip().lstrip(".#")
    if not style_name or not _is_style_name(style_name):
        return False

    if silent:
        return True

    inner_tokens = state.md.parseInline(label, state.env)
    state.pushPending()

    open_token = Token("dfm_styled_open", "", 0)
    open_token.attrSet("style", style_name)
    state.tokens.append(open_token)
    if inner_tokens:
        state.tokens.extend(inner_tokens[0].children or [])
    state.pushPending()
    state.tokens.append(Token("dfm_styled_close", "", 0))

    state.pos = brace_end + 1
    return True


def rule_math(state: StateInline, silent: bool) -> bool:
    """``$latex$`` 与 ``$$latex$$``；内容原样保留，内部不解析 Markdown。"""
    src = state.src
    if src[state.pos] != "$":
        return False

    if src[state.pos : state.pos + 2] == "$$":
        closing = src.find("$$", state.pos + 2)
        if closing == -1:
            return False
        latex = src[state.pos + 2 : closing]
        display = True
        end = closing + 2
    else:
        closing = src.find("$", state.pos + 1)
        if closing == -1:
            return False
        latex = src[state.pos + 1 : closing]
        if not latex.strip():
            return False
        display = False
        end = closing + 1

    if silent:
        return True

    token = Token("dfm_math", "", 0)
    token.content = latex
    token.meta = {"display": display}
    state.pushPending()
    state.tokens.append(token)
    state.pos = end
    return True


def rule_script(state: StateInline, silent: bool) -> bool:
    """上下标（Pandoc 风格）：``H~2~O`` 下标、``E=mc^2^`` 上标。

    ``~~`` 留给删除线（markdown-it 的 strikethrough），所以这里排除双写；
    内容不允许含空白与换行，避免把普通文本里的 ``~`` / ``^`` 误当标记。
    """
    src = state.src
    marker = src[state.pos]
    if marker not in ("~", "^"):
        return False
    if src[state.pos : state.pos + 2] == marker * 2:
        return False

    closing = src.find(marker, state.pos + 1)
    if closing == -1:
        return False

    content = src[state.pos + 1 : closing]
    if not content or content != content.strip() or any(ch.isspace() for ch in content):
        return False

    if silent:
        return True

    token = Token("dfm_script", "", 0)
    token.content = content
    token.meta = {"script": "sub" if marker == "~" else "sup"}
    state.pushPending()
    state.tokens.append(token)
    state.pos = closing + 1
    return True


def _is_style_name(name: str) -> bool:
    """样式名允许字母、数字与 ``_ - .``（点用于命名空间）。"""
    return all(ch.isalnum() or ch in "_-." for ch in name)


def register_rules(md: MarkdownIt) -> None:
    md.inline.ruler.before("escape", "dfm_wiki", rule_wiki)
    md.inline.ruler.before("escape", "dfm_math", rule_math)
    md.inline.ruler.before("escape", "dfm_styled", rule_styled)
    # 上下标要在 text 之前：``~`` / ``^`` 不在 text 规则的 specialChars 里，
    # 不显式加入的话「无特殊字符」快速路径会让规则根本不被调用。
    md.inline.ruler.before("text", "dfm_script", rule_script)
    _add_special_chars(md, "~^")


def _add_special_chars(md: MarkdownIt, chars: str) -> None:
    """把字符加进 text 规则的 specialChars，否则快速路径会直接当成纯文本。"""
    for rule in md.inline.ruler2.getRules(""):
        if getattr(rule, "name", "") == "text":
            current = getattr(rule, "specialChars", "")
            rule.specialChars = "".join(dict.fromkeys(current + chars))  # type: ignore[attr-defined]

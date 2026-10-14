"""config 解析（手册 §5.3 / 第 2 周）。

一份 config 由若干 TOML 文件合并而来：``include`` 先合并、后者覆盖前者、自身最后覆盖。
合并后的 ``[styles.*]`` / ``[code_block]`` / ``[code_block.<lang>]`` 支持单继承
``based_on``（浅合并、子覆盖父、子值为 ``false`` 表示删除父值）与 ``@引用``
（可指向 ``[document]``、``[styles.*]`` 或 ``[code_block]``）。

错误码：

- ``E5001`` 文件缺失 / 非法读取 / 版本不符 / ``based_on`` 指向不存在的样式
- ``E1001`` 循环继承或循环引用
- ``E1002`` 继承深度超限（上限 8）
- ``E1003`` ``@ref`` 指向不存在的键
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .errors import (
    E_CIRCULAR_INHERITANCE,
    E_CONFIG,
    E_INHERITANCE_DEPTH,
    E_UNKNOWN_STYLE,
    DocGenError,
)

CONFIG_VERSION = "0.1"
MAX_INHERITANCE_DEPTH = 8

#: 解析器会产生的内置样式名（``**粗体**`` / ``*斜体*`` / ``~~删除~~`` / ``H~2~O`` / ``E=mc^2^``）。
#: config 没声明它们时按空属性处理，保证「引用不存在的样式」不会误报。
BUILTIN_STYLES = ("strong", "em", "strike", "sup", "sub")

#: ``[inline]`` 段可重定向的语义名（与 ``BUILTIN_STYLES`` 同集合）
INLINE_STYLE_NAMES = BUILTIN_STYLES

#: 语义名 -> 实际样式名 的映射（默认同名）
InlineMapping = dict[str, str]

__all__ = [
    "BUILTIN_STYLES",
    "CONFIG_VERSION",
    "INLINE_STYLE_NAMES",
    "MAX_INHERITANCE_DEPTH",
    "Config",
    "InlineMapping",
    "Style",
    "build_style_table",
    "build_style_tree",
    "load_config",
    "render_table",
]

Table = dict[str, Any]
Properties = dict[str, Any]


@dataclass(frozen=True)
class Style:
    """一条样式声明（未展开）：``properties`` 是自身属性，不含 ``based_on``。"""

    name: str
    properties: Properties
    based_on: str | None = None


@dataclass(frozen=True)
class Config:
    version: str
    document: Properties
    styles: dict[str, Style]
    code_block: Properties
    code_blocks: dict[str, Properties]
    #: 其它顶层命名空间（``[table]`` / ``[math]`` / ``[image]`` / ``[page]``…）；
    #: 渲染层按需取用，不参与样式继承
    extra: Table = field(default_factory=dict)
    raw: Table = field(default_factory=dict, repr=False)

    def setting(self, key: str, default: Any = None) -> Any:
        """按点号路径取设置，**同时支持**扁平键与嵌套表两种写法。

        ``document.setting("hr.style")`` 对下面两种 config 都成立：

        ```toml
        [document]
        hr.style = "double"     # 扁平点号键
        ```
        ```toml
        [document.hr]
        style = "double"        # 嵌套表
        ```

        ``[document]`` 里的点号键**不会**被展开成嵌套表（只有样式属性会），
        所以取值必须两条路径都试——否则 `hr.style = "double"` 会被静默忽略。
        """
        if key in self.document:
            return self.document[key]
        current: Any = self.document
        for part in key.split("."):
            if not isinstance(current, dict) or part not in current:
                return default
            current = current[part]
        return current

    # ---- 命名空间查询（供「是否显式声明过」这类判断）-------------------
    def namespace(self, name: str) -> Table:
        """取一个顶层命名空间表；不存在或不是表时返回空表。"""
        value = self.extra.get(name)
        return dict(value) if isinstance(value, dict) else {}

    def declares(self, namespace: str, key: str) -> bool:
        """配置里是否**显式声明**了 ``[namespace] key``（用于默认值提示）。

        例：``[table] style`` 没写时返回 False —— 引擎据此提示「用了默认三线表」。
        支持 ``key.sub`` 形式的嵌套写法。
        """
        table = self.namespace(namespace)
        if not table:
            return False
        if key in table:
            return True
        current: Any = table
        for part in key.split("."):
            if not isinstance(current, dict) or part not in current:
                return False
            current = current[part]
        return True

    def inline_mapping(self) -> InlineMapping:
        """``[inline]`` 段：Markdown/DFM 语义名 -> 实际样式名。

        **默认同名**，所以不写 ``[inline]`` 时行为完全不变；写了就能重定向，
        例如 ``sup = "sup_caret"`` 会让 ``^x^`` 走 ``[styles.sup_caret]``。
        """
        declared = self.namespace("inline")
        return {name: str(declared.get(name, name)) for name in INLINE_STYLE_NAMES}

    def inline_style_name(self, semantic: str) -> str:
        """解析一个语义名到实际样式名（未映射则同名）。"""
        return self.inline_mapping().get(semantic, semantic)

    def has_style(self, name: str) -> bool:
        """config 是否声明了该样式（``[styles.<name>]``）。"""
        return name in self.styles


class _LinkError(Exception):
    """config 内部错误：在 :func:`build_style_table` 边界统一转成 ``DocGenError``。"""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


# --------------------------------------------------------------------------
# 读取与合并
# --------------------------------------------------------------------------
def load_config(path: Path) -> Config:
    """加载 config（含 ``include`` 递归合并），返回尚未展开继承的 :class:`Config`。"""
    merged = _load_merged(path, seen=set())
    version = merged.get("config_version")
    if version is None:
        raise DocGenError(
            E_CONFIG,
            f"config 缺少 config_version（期望 {CONFIG_VERSION!r}）",
            file=str(path),
        )
    if version != CONFIG_VERSION:
        raise DocGenError(
            E_CONFIG,
            f"config 版本不符：期望 {CONFIG_VERSION!r}，实际 {version!r}",
            file=str(path),
        )
    base, languages = _code_blocks_of(merged)
    return Config(
        version=version,
        document=_table(merged.get("document")),
        styles=_styles_of(merged),
        code_block=base,
        code_blocks=languages,
        extra=_extra_of(merged),
        raw=merged,
    )


#: 已由专门字段承载的顶层键
_RESERVED_TABLES = frozenset({"config_version", "include", "document", "styles", "code_block"})


def _extra_of(merged: Table) -> Table:
    """收集其它顶层命名空间：``[table]``/``[math]``/``[image]``（表）与
    ``[[sections]]``（表数组）。"""
    extra: Table = {}
    for key, value in merged.items():
        if key in _RESERVED_TABLES:
            continue
        if isinstance(value, dict) or (
            isinstance(value, list) and value and all(isinstance(item, dict) for item in value)
        ):
            extra[str(key)] = value
    return extra


def _read_toml(path: Path) -> Table:
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        raise DocGenError(E_CONFIG, f"config 文件不存在: {path}") from None
    except OSError as exc:
        raise DocGenError(E_CONFIG, f"无法读取 config: {path}: {exc}") from None
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DocGenError(E_CONFIG, f"config 不是合法 UTF-8: {path}: {exc}") from None
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise DocGenError(E_CONFIG, f"config 解析失败: {path}: {exc}") from None
    return data


def _load_merged(path: Path, seen: set[Path]) -> Table:
    key = path.resolve()
    if key in seen:
        raise DocGenError(E_CONFIG, f"include 出现循环: {path}")
    seen.add(key)
    try:
        local = _read_toml(path)
        includes = local.get("include", [])
        if not isinstance(includes, list) or not all(isinstance(i, str) for i in includes):
            raise DocGenError(E_CONFIG, f"include 必须是字符串数组: {path}")

        merged: Table = {}
        for name in includes:
            merged = _merge(merged, _load_merged(path.parent / name, seen))
        return _merge(merged, {k: v for k, v in local.items() if k != "include"})
    finally:
        seen.discard(key)


def _merge(base: Table, override: Table) -> Table:
    """浅合并两个表，``override`` 的同名键覆盖 ``base``。"""
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = value
    return result


def _table(value: Any) -> Table:
    if value is None:
        return {}
    if isinstance(value, dict):
        return {str(k): v for k, v in value.items()}
    raise DocGenError(E_CONFIG, f"config 中期望一个表，实际是 {type(value).__name__}")


def _styles_of(merged: Table) -> dict[str, Style]:
    styles: dict[str, Style] = {}
    for name, value in _table(merged.get("styles")).items():
        if not isinstance(value, dict):
            raise DocGenError(E_CONFIG, f"styles.{name} 必须是表")
        based_on = value.get("based_on")
        if based_on is not None and not isinstance(based_on, str):
            raise DocGenError(E_CONFIG, f"styles.{name}.based_on 必须是字符串")
        styles[name] = Style(
            name=name,
            properties={k: v for k, v in value.items() if k != "based_on"},
            based_on=based_on,
        )
    return styles


def deep_merge(base: Properties, override: Properties) -> Properties:
    """递归合并样式属性：嵌套表（``font.color`` 展开成 ``{"font": {...}}``）逐层合并。

    浅合并（``dict.update``）会让 ``[code_block]`` 的 ``font`` 整个盖掉
    ``[code_block.python]`` 的 ``font.color``——**配置看起来没生效**（实测踩到）。
    """
    merged: Properties = dict(base)
    for key, value in override.items():
        current = merged.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            merged[key] = deep_merge(current, value)
        else:
            merged[key] = value
    return merged


#: ``[code_block]`` 下属于「基座配置」的子命名空间（点号键展开后会变成嵌套表）。
#: 例如 ``font.name = "Consolas"`` 解析成 ``code_block.font``——它**不是**语言变体。
_CODE_BLOCK_SUBNAMESPACES = frozenset({"font", "spacing", "border", "background", "shading"})


def _code_blocks_of(merged: Table) -> tuple[Properties, dict[str, Properties]]:
    """把 ``[code_block]`` 拆成「基座属性」与「语言变体子表」。

    判据不能是「值是不是表」——点号键（``font.name``）展开后也是表，
    曾被误判成语言 ``font``，导致基座的字体/字号凭空丢失（实测踩到）。
    """
    namespace = _table(merged.get("code_block"))
    base = {
        key: value
        for key, value in namespace.items()
        if not isinstance(value, dict) or key in _CODE_BLOCK_SUBNAMESPACES
    }
    languages = {
        str(key): {k: v for k, v in value.items()}
        for key, value in namespace.items()
        if isinstance(value, dict) and key not in _CODE_BLOCK_SUBNAMESPACES
    }
    return base, languages


# --------------------------------------------------------------------------
# 继承 + @ref 展开
# --------------------------------------------------------------------------
def build_style_table(config: Config) -> dict[str, Properties]:
    """把 config 展开成「最终值」符号表：先算继承链，再解析 ``@ref``。

    返回结构以样式名为键、最终属性为值（确定性顺序），包含 ``[styles.*]``、
    ``document``、``code_block`` 与每个语言变体 ``code_block.<lang>``。

    语言变体**必须键名为** ``code_block.<lang>``：渲染层按这个名字查
    （``state.styles["code_block.python"]``），以前登记成裸 ``python`` 导致
    ``[code_block.python]`` 的配置永远读不到（实测踩到）。
    """
    renumbered, symbols = _expand(config)
    try:
        styles = {name: _resolve_properties(renumbered[name], symbols) for name in renumbered}
        for language in config.code_blocks:
            styles[f"code_block.{language}"] = styles.pop(language)
        table: dict[str, Properties] = {
            "document": _resolve_properties(config.document, symbols),
            **{name: styles[name] for name in sorted(styles)},
        }
    except _LinkError as err:
        raise DocGenError(err.code, err.message) from None
    return table


def build_style_tree(config: Config) -> Table:
    """展开后的样式树，形状与 config 一致（``document`` / ``styles`` / ``code_block``）。

    额外步骤：按 ``[inline]`` 把**语义名**指向实际样式名，让渲染层用
    ``tree["styles"]["sup"]`` 也能取到重定向后的 ``sup_caret``。
    """
    renumbered, symbols = _expand(config)
    try:
        code_block: Table = dict(_resolve_properties(config.code_block, symbols))
        for name in sorted(config.code_blocks):
            code_block[name] = _resolve_properties(renumbered[name], symbols)

        styles: Table = {
            name: _resolve_properties(renumbered[name], symbols) for name in sorted(config.styles)
        }
        # ``[inline]`` 重定向：语义名 -> 实际样式名，两边都留一份，渲染层无需感知映射
        for semantic, target in config.inline_mapping().items():
            if target != semantic and target in styles and semantic not in styles:
                styles[semantic] = styles[target]

        tree: Table = {"styles": styles, "code_block": code_block}
        if config.document:
            tree["document"] = _resolve_properties(config.document, symbols)
    except _LinkError as err:
        raise DocGenError(err.code, err.message) from None
    return tree


def _expand(config: Config) -> tuple[dict[str, Properties], Table]:
    """算出所有样式的继承结果，并构造 ``@ref`` 用的嵌套符号表。"""
    try:
        renumbered = {name: _resolve_style(name, config, []) for name in _style_names(config)}
    except _LinkError as err:
        raise DocGenError(err.code, err.message) from None

    symbols: Table = {
        "document": dict(config.document),
        "styles": {name: renumbered[name] for name in config.styles},
        "code_block": {
            **config.code_block,
            **{name: renumbered[name] for name in config.code_blocks},
        },
    }
    return renumbered, symbols


def _resolve_properties(properties: Properties, symbols: Table) -> Properties:
    """展开一条样式/命名空间的属性；点号键展开成嵌套表。

    点号键是手册 §6.1 的写法（``font.name`` / ``font.bold``），所以展开后的值
    保持嵌套结构，渲染层按 ``properties["font"]["name"]`` 读取。
    """
    resolved: Properties = {}
    for key, value in sorted(properties.items()):
        target = resolved
        parts = key.split(".")
        for part in parts[:-1]:
            child = target.setdefault(part, {})
            if not isinstance(child, dict):
                raise DocGenError(E_CONFIG, f"键冲突：{key} 与已有的 {part} 不能同时存在")
            target = child
        target[parts[-1]] = _resolve_ref(value, symbols, [])
    return resolved


def _style_names(config: Config) -> list[str]:
    declared = [*config.styles, "code_block", *config.code_blocks]
    builtin = [name for name in BUILTIN_STYLES if name not in config.styles]
    return [*declared, *builtin]


def _resolve_style(name: str, config: Config, stack: list[str]) -> Properties:
    if name in stack:
        chain = " -> ".join([*stack, name])
        raise _LinkError(E_CIRCULAR_INHERITANCE, f"循环继承: {chain}")
    if len(stack) >= MAX_INHERITANCE_DEPTH:
        raise _LinkError(E_INHERITANCE_DEPTH, f"继承深度超过 {MAX_INHERITANCE_DEPTH}: {name}")

    raw = _declaration(name, config)
    if raw is None:
        raise _LinkError(E_CONFIG, f"based_on 指向不存在的样式: {name}")

    parent_name = raw.get("based_on")
    parent: Properties = {}
    if isinstance(parent_name, str):
        parent = _resolve_style(parent_name, config, [*stack, name])

    merged = dict(parent)
    for key, value in raw.items():
        if key == "based_on":
            continue
        if value is False:
            merged.pop(key, None)  # for = false 软删除
        else:
            merged[key] = value
    return merged


def _declaration(name: str, config: Config) -> Table | None:
    """取一条样式的原始声明：``[styles.x]`` / ``[code_block]`` / ``[code_block.<lang>]``。"""
    if name == "code_block":
        return dict(config.code_block)

    if name in config.code_blocks:
        return {"based_on": "code_block", **config.code_blocks[name]}

    style = config.styles.get(name)
    if style is None:
        if name in BUILTIN_STYLES:
            return {}  # 内置样式未声明 = 无额外属性
        return None
    declaration = dict(style.properties)
    if style.based_on is not None:
        declaration["based_on"] = style.based_on
    return declaration


def _resolve_ref(value: Any, symbols: Table, stack: list[str]) -> Any:
    """``@a.b.c`` 解析为实际值；支持链式引用。"""
    if not isinstance(value, str) or not value.startswith("@"):
        return value

    path = value[1:]
    if path in stack:
        raise _LinkError(E_CIRCULAR_INHERITANCE, f"循环引用: {' -> '.join([*stack, path])}")

    current: Any = symbols
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            raise _LinkError(E_UNKNOWN_STYLE, f"引用不存在的键: {value}")
        current = current[part]

    return _resolve_ref(current, symbols, [*stack, path])


# --------------------------------------------------------------------------
# 输出（确定性）
# --------------------------------------------------------------------------
def render_table(table: Table, header: str = "") -> str:
    """把嵌套字典渲染成确定性 TOML：键排序、两空格缩进、表头按路径拼接。

    只用于 ``dump-styles`` 的展示，不保证覆盖 TOML 的全部写法（数组/日期按字面输出）。
    """
    lines: list[str] = []
    _render_section(table, header, lines)
    return "\n".join(lines) + ("\n" if lines else "")


def _render_section(table: Table, header: str, lines: list[str]) -> None:
    scalars = [(key, table[key]) for key in sorted(table) if not isinstance(table[key], dict)]
    children = [(key, table[key]) for key in sorted(table) if isinstance(table[key], dict)]

    if header and (scalars or not children):
        lines.append(f"[{header}]")
    for key, value in scalars:
        lines.append(f"{key} = {_render_value(value)}")
    if scalars and children:
        lines.append("")

    for index, (key, child) in enumerate(children):
        path = f"{header}.{key}" if header else key
        _render_section(child, path, lines)
        if index != len(children) - 1:
            lines.append("")


def _render_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    if isinstance(value, int | float):
        return str(value)
    return f'"{value}"'

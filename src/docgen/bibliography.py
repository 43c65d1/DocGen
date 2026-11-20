"""文献引用（顺序编码制，GB/T 7714 风格）。

能力边界（方案 A）：

- ``[[cite:key1,key2]]`` 行内引用 → ``[1]`` / ``[1,2]`` / ``[1-3]``；
  编号按**首次出现顺序**分配，构建期烘焙（不依赖 Word 域）。
- 文献库是独立 TOML 文件（``--refs`` 或 ``[bibliography] file``），
  条目形如 ``[zhang2024] type = "article" author = ...``。
- ``[[bibliography]]`` 指定参考文献表位置；不写则自动追加到文末。
- 只做 GB/T 7714 **顺序编码制**的常见类型（期刊/专著/会议/学位论文/标准/电子资源），
  不做 BibTeX 完整语法、不做 CSL 多风格引擎。
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import Config
from .encoding import decode_text
from .errors import E_CONFIG, E_SYNTAX, E_UNKNOWN_REF, DocGenError
from .ir import (
    Bibliography,
    BlockNode,
    BlockQuote,
    Cite,
    Heading,
    ListBlock,
    NamedBlock,
    Paragraph,
    Styled,
    Table,
)
from .validate import ContentError

__all__ = [
    "BibliographyPlan",
    "BibliographySettings",
    "bibliography_settings",
    "citation_text",
    "collect_citations",
    "format_reference",
    "has_bibliography_marker",
    "load_references",
    "plan_bibliography",
    "resolve_refs_path",
    "validate_bibliography",
]

#: GB/T 7714 文献类型标识
TYPE_MARKS = {
    "article": "J",
    "journal": "J",
    "book": "M",
    "monograph": "M",
    "conference": "C",
    "proceedings": "C",
    "thesis": "D",
    "dissertation": "D",
    "standard": "S",
    "online": "EB/OL",
    "electronic": "EB/OL",
    "report": "R",
    "patent": "P",
    "newspaper": "N",
}


@dataclass(frozen=True, slots=True)
class BibliographyPlan:
    """一次构建的文献编号与条目（按首次引用顺序）。"""

    title: str
    numbers: dict[str, int] = field(default_factory=dict)
    entries: tuple[str, ...] = ()
    #: 条目是否带 ``[n]`` 前缀（顺序编码制默认带）
    entry_number: bool = True
    #: 正文 ``[[cite:]]`` 上标
    citation_superscript: bool = False
    #: 条目悬挂缩进（字符数）
    hanging_chars: int = 0


@dataclass(frozen=True, slots=True)
class BibliographySettings:
    """``[bibliography]`` 的规范化设置。"""

    title: str = "参考文献"
    entry_number: bool = True
    citation_superscript: bool = False
    hanging_chars: int = 0
    author_truncate: int = 0
    et_al: str = ""
    western_initials: bool = False


def _bool_setting(settings: dict[str, Any], key: str, default: bool) -> bool:
    value = settings.get(key)
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in ("true", "1", "yes", "on"):
        return True
    if text in ("false", "0", "no", "off"):
        return False
    raise DocGenError(E_CONFIG, f"[bibliography] {key} 需要 true/false，收到 {value!r}")


def _int_setting(settings: dict[str, Any], key: str, default: int) -> int:
    value = settings.get(key)
    if value is None:
        return default
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise DocGenError(E_CONFIG, f"[bibliography] {key} 需要整数，收到 {value!r}") from None
    if number < 0:
        raise DocGenError(E_CONFIG, f"[bibliography] {key} 不能为负数，收到 {value!r}")
    return number


def bibliography_settings(config: Config) -> BibliographySettings:
    """解析 ``[bibliography]``：条目编号 / 引用上标 / 悬挂缩进 / 作者截断。"""
    raw = config.namespace("bibliography")
    return BibliographySettings(
        title=str(raw.get("title", "参考文献") or "参考文献"),
        entry_number=_bool_setting(raw, "entry_number", True),
        citation_superscript=_bool_setting(raw, "citation_superscript", False),
        hanging_chars=_int_setting(raw, "hanging_chars", 0),
        author_truncate=_int_setting(raw, "author_truncate", 0),
        et_al=str(raw.get("et_al", "") or ""),
        western_initials=_bool_setting(raw, "western_initials", False),
    )


# --------------------------------------------------------------------------
# 文献库
# --------------------------------------------------------------------------
def load_references(path: Path) -> dict[str, dict[str, Any]]:
    """读取 TOML 文献库：每个条目是 ``[key]`` 表。

    编码走 :func:`docgen.encoding.decode_text`（UTF-8 优先、GB18030 兜底）——
    之前直接 ``read_text(encoding="utf-8")``，GBK 文件会抛未捕获的
    ``UnicodeDecodeError``。
    """
    try:
        raw_bytes = path.read_bytes()
    except OSError as exc:
        raise DocGenError(E_CONFIG, f"无法读取文献库: {path}: {exc}") from None
    raw = decode_text(raw_bytes, path=str(path))
    try:
        data = tomllib.loads(raw)
    except tomllib.TOMLDecodeError as exc:
        raise DocGenError(E_CONFIG, f"文献库 TOML 解析失败: {path}: {exc}") from None

    references: dict[str, dict[str, Any]] = {}
    for key, value in data.items():
        if not isinstance(value, dict):
            raise DocGenError(
                E_CONFIG,
                f"文献库条目 {key!r} 必须是表（[{key}] 形式），收到 {type(value).__name__}",
            )
        references[key] = dict(value)
    return references


def resolve_refs_path(
    config: Config, base_dir: Path | None, override: Path | None = None
) -> Path | None:
    """文献库路径：``--refs`` 优先，其次 ``[bibliography] file``。

    相对路径按**输入文件所在目录**（``base_dir``）解析，与图片路径一致。
    """
    if override is not None:
        return Path(override)
    settings = config.namespace("bibliography")
    value = settings.get("file")
    if not value:
        return None
    path = Path(str(value))
    if path.is_absolute():
        return path
    return (base_dir or Path()) / path


# --------------------------------------------------------------------------
# 收集引用
# --------------------------------------------------------------------------
def collect_citations(blocks: list[BlockNode]) -> list[tuple[str, int]]:
    """按文档顺序返回 ``(key, source_line)``（重复引用会出现多次）。"""
    found: list[tuple[str, int]] = []

    def walk_inlines(nodes: list[Any], line: int) -> None:
        for node in nodes:
            if isinstance(node, Cite):
                if not node.keys:
                    # 记录空标记，让 validate 报「缺少 key」（正常渲染路径 plan 会报错）
                    found.append(("", line))
                for key in node.keys:
                    found.append((key, line))
            elif isinstance(node, Styled):
                walk_inlines(node.content, line)

    def walk_blocks(nodes: list[BlockNode], fallback: int) -> None:
        for node in nodes:
            line = node.source_line or fallback
            if isinstance(node, (Paragraph, Heading)):
                walk_inlines(node.content, line)
            elif isinstance(node, (NamedBlock, BlockQuote)):
                walk_blocks(node.content, line)
            elif isinstance(node, ListBlock):
                for item in node.items:
                    walk_blocks(item.content, line)
            elif isinstance(node, Table):
                for row in node.cell_nodes:
                    for cell in row:
                        walk_inlines(cell, line)

    walk_blocks(blocks, 0)
    return found


def _bibliography_markers(blocks: list[BlockNode]) -> list[int]:
    """递归收集 ``[[bibliography]]`` 标记的源行号（含嵌套块）。"""
    lines: list[int] = []

    def walk(nodes: list[BlockNode]) -> None:
        for node in nodes:
            if isinstance(node, Bibliography):
                lines.append(node.source_line)
            elif isinstance(node, (NamedBlock, BlockQuote)):
                walk(node.content)
            elif isinstance(node, ListBlock):
                for item in node.items:
                    walk(item.content)

    walk(blocks)
    return lines


def has_bibliography_marker(blocks: list[BlockNode]) -> bool:
    """文档里是否显式写了 ``[[bibliography]]``（决定是否自动追加）。"""
    return bool(_bibliography_markers(blocks))


# --------------------------------------------------------------------------
# 规划（编号 + 条目）
# --------------------------------------------------------------------------
def plan_bibliography(
    blocks: list[BlockNode],
    config: Config,
    *,
    base_dir: Path | None = None,
    refs: Path | None = None,
) -> BibliographyPlan | None:
    """分配编号并生成条目；无引用时返回 ``None``（不生成空表）。"""
    citations = collect_citations(blocks)
    if not citations:
        return None
    if any(not key for key, _line in citations):
        raise DocGenError(E_SYNTAX, "[[cite:]] 缺少文献 key")

    path = resolve_refs_path(config, base_dir, refs)
    if path is None:
        raise DocGenError(
            E_CONFIG,
            '文档里有 [[cite:...]]，但没有指定文献库：用 --refs 或 [bibliography] file = "refs.toml"',
        )
    references = load_references(path)

    numbers: dict[str, int] = {}
    for key, _line in citations:
        if key not in numbers:
            if key not in references:
                raise DocGenError(E_UNKNOWN_REF, f"引用不存在: {key}")
            numbers[key] = len(numbers) + 1

    settings = bibliography_settings(config)
    entries: list[str] = []
    for key, number in numbers.items():
        body = format_reference(
            references[key],
            number,
            truncate=settings.author_truncate,
            et_al=settings.et_al,
            western_initials=settings.western_initials,
        )
        entries.append(f"[{number}] {body}" if settings.entry_number else body)
    return BibliographyPlan(
        title=settings.title,
        numbers=numbers,
        entries=tuple(entries),
        entry_number=settings.entry_number,
        citation_superscript=settings.citation_superscript,
        hanging_chars=settings.hanging_chars,
    )


def validate_bibliography(
    blocks: list[BlockNode],
    config: Config,
    *,
    source: Path | None = None,
    base_dir: Path | None = None,
    refs: Path | None = None,
) -> list[ContentError]:
    """与 :func:`plan_bibliography` 同规则，但返回错误列表（供 ``check`` 用）。"""
    errors: list[ContentError] = []
    file_name = str(source) if source is not None else ""
    try:
        bibliography_settings(config)
    except DocGenError as err:
        errors.append(ContentError(code=err.code, message=str(err), file=file_name, line=0))

    markers = _bibliography_markers(blocks)
    if len(markers) > 1:
        errors.append(
            ContentError(
                code=E_SYNTAX,
                message="[[bibliography]] 只能出现一次",
                file=file_name,
                line=markers[1],
            )
        )

    citations = collect_citations(blocks)
    if not citations:
        return errors
    empty = [line for key, line in citations if not key]
    if empty:
        errors.append(
            ContentError(
                code=E_SYNTAX,
                message="[[cite:]] 缺少文献 key",
                file=file_name,
                line=empty[0],
            )
        )
        return errors

    path = resolve_refs_path(config, base_dir, refs)
    if path is None:
        errors.append(
            ContentError(
                code=E_CONFIG,
                message='有 [[cite:...]] 但没有文献库：用 --refs 或 [bibliography] file = "refs.toml"',
                file=file_name,
                line=citations[0][1],
            )
        )
        return errors
    try:
        references = load_references(path)
    except DocGenError as err:
        errors.append(ContentError(code=err.code, message=str(err), file=file_name, line=0))
        return errors

    seen: set[str] = set()
    for key, line in citations:
        if key in seen:
            continue
        seen.add(key)
        if key not in references:
            errors.append(
                ContentError(
                    code=E_UNKNOWN_REF,
                    message=f"引用不存在: {key}（文献库 {path.name} 里没有该条目）",
                    file=file_name,
                    line=line,
                )
            )
    return errors


# --------------------------------------------------------------------------
# 引用文本
# --------------------------------------------------------------------------
def citation_text(keys: tuple[str, ...], numbers: dict[str, int]) -> str:
    """``('a','b','c')`` → ``[1,2,3]``；连续 3 个及以上压成 ``[1-3]``。"""
    nums = sorted({numbers[key] for key in keys if key in numbers})
    if not nums:
        return ""
    runs: list[list[int]] = []
    for number in nums:
        if runs and number == runs[-1][-1] + 1:
            runs[-1].append(number)
        else:
            runs.append([number])
    pieces: list[str] = []
    for run in runs:
        if len(run) >= 3:
            pieces.append(f"{run[0]}-{run[-1]}")
        else:
            pieces.extend(str(item) for item in run)
    return "[" + ",".join(pieces) + "]"


# --------------------------------------------------------------------------
# GB/T 7714 条目格式化
# --------------------------------------------------------------------------
def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


_CJK_RE = re.compile(r"[\u3400-\u9fff\uf900-\ufaff]")


#: 西文姓名的后缀（不算作姓氏）
_NAME_SUFFIXES = frozenset({"jr", "jr.", "sr", "sr.", "ii", "iii", "iv"})


def _western_name(name: str) -> str:
    """西文作者 → GB/T 7714「姓前名后、姓大写、名缩写」：``John A. Hewitt`` → ``HEWITT J A``。

    输入兼容三种常见写法：

    | 写法 | 输出 |
    |---|---|
    | ``Surname, Given`` | ``SURNAME I I`` |
    | ``Given ... Surname`` | ``SURNAME I I`` |
    | ``Surname I`` / ``Surname I.I.`` | ``SURNAME I I`` |

    中文姓名（含 CJK 字符）原样返回——本函数只处理西文姓名的书写顺序与缩写。

    已知边界：拼音姓名（``Li Ming``）按西文规则会被当成「名 Li、姓 Ming」，
    要保持「姓前名后」请写成 ``Li, Ming``；van/de 之类的姓氏前缀会一起大写
    （``VAN DER WAALS J``）。
    """
    text = name.strip()
    if not text or _CJK_RE.search(text):
        return text

    tokens = text.split()
    suffix = ""
    if tokens and tokens[-1].lower() in _NAME_SUFFIXES:
        suffix = tokens.pop()
    if not tokens:
        return text

    if "," in " ".join(tokens):
        # ``Surname, Given ...``：逗号前是姓
        head, _, tail = " ".join(tokens).partition(",")
        surname = head.strip()
        given = tail.strip()
    else:
        last = tokens[-1]
        if _looks_like_initials(last):
            surname = " ".join(tokens[:-1])
            given = last
        else:
            surname = last
            given = " ".join(tokens[:-1])

    if not surname:
        return text
    parts = [surname.upper(), _initials(given), suffix]
    return " ".join(part for part in parts if part)


def _looks_like_initials(token: str) -> bool:
    """``A`` / ``J.A.`` / ``JA`` / ``J-A``：名已经缩写的写法（姓氏在它**前面**）。"""
    letters = [char for char in token if char.isalpha()]
    if not letters or len(letters) > 3:
        return False
    return all(char.isupper() for char in letters)


def _initials(given: str) -> str:
    """名 → 缩写：按空格 / 点 / 连字符切分，每段首字母大写，用空格连接。"""
    letters: list[str] = []
    for chunk in re.split(r"[\s.\-]+", given):
        if not chunk:
            continue
        if chunk.isalpha() and chunk.isupper() and len(chunk) <= 3:
            # 已经是缩写：``JA`` / ``J`` 原样拆成单个字母
            letters.extend(chunk)
        elif chunk[0].isalpha():
            letters.append(chunk[0].upper())
    return " ".join(letters)


def _authors(
    value: Any, *, truncate: int = 0, et_al: str = "", western_initials: bool = False
) -> str:
    """作者列表 → 字符串；``truncate > 0`` 时按 GB/T「前 N 名 + 等/et al」。

    ``western_initials = true`` 时先把西文姓名转成「姓大写 + 名缩写」
    （中文姓名不动），再按截断规则拼接。
    """
    if isinstance(value, (list, tuple)):
        names = [part for part in (_text(item) for item in value) if part]
        if western_initials:
            names = [_western_name(name) for name in names]
        if truncate > 0 and len(names) > truncate:
            kept = names[:truncate]
            suffix = et_al or ("等" if any(_CJK_RE.search(name) for name in kept) else "et al.")
            return ", ".join(kept) + ", " + suffix
        return ", ".join(names)
    text = _text(value)
    return _western_name(text) if western_initials else text


def _join(values: list[str], sep: str = ", ") -> str:
    return sep.join(value for value in values if value)


def _tail(values: list[str], pages: str = "") -> str:
    """拼接「出版项」，页码用 ``:`` 接在最后。"""
    text = _join(values)
    if pages:
        return f"{text}: {pages}" if text else pages
    return text


def format_reference(
    entry: dict[str, Any],
    number: int,
    *,
    truncate: int = 0,
    et_al: str = "",
    western_initials: bool = False,
) -> str:
    """格式化单条文献（不含序号），返回类似 ``张三. 标题[J]. 期刊, 2024, 12(3): 45-52.``。"""
    kind = _text(entry.get("type")).lower() or "misc"
    mark = TYPE_MARKS.get(kind, "")
    authors = _authors(
        entry.get("author"), truncate=truncate, et_al=et_al, western_initials=western_initials
    )
    title = _text(entry.get("title"))
    year = _text(entry.get("year"))
    pages = _text(entry.get("pages"))
    place = _text(entry.get("place"))
    publisher = _text(entry.get("publisher"))
    journal = _text(entry.get("journal"))
    volume = _text(entry.get("volume"))
    issue = _text(entry.get("issue"))
    school = _text(entry.get("school"))
    conference = _text(entry.get("conference")) or _text(entry.get("booktitle"))
    date = _text(entry.get("date"))
    cited = _text(entry.get("cited"))
    url = _text(entry.get("url"))
    doi = _text(entry.get("doi"))

    chunks: list[str] = []
    if authors:
        chunks.append(authors)
    head = f"{title}[{mark}]" if title and mark else title
    if kind == "standard":
        standard_number = _text(entry.get("number"))
        if standard_number:
            head = f"{standard_number} {title}[S]" if title else f"{standard_number}[S]"
    if kind in ("conference", "proceedings") and head:
        head += f"//{conference}" if conference else ""
    if head:
        chunks.append(head)

    if kind in ("article", "journal"):
        pub: list[str] = []
        if journal:
            pub.append(journal)
        if year:
            pub.append(year)
        volume_part = volume + (f"({issue})" if issue else "")
        if volume_part:
            pub.append(volume_part)
        else:
            if issue:
                pub.append(f"({issue})")
        tail = _tail(pub, pages)
        if tail:
            chunks.append(tail)
    elif kind in ("book", "monograph"):
        pub = []
        if place and publisher:
            pub.append(f"{place}: {publisher}")
        elif publisher:
            pub.append(publisher)
        if year:
            pub.append(year)
        if pub:
            chunks.append(", ".join(pub))
    elif kind in ("conference", "proceedings"):
        pub = []
        if place and publisher:
            pub.append(f"{place}: {publisher}")
        elif publisher:
            pub.append(publisher)
        if year:
            pub.append(year)
        tail = _tail(pub, pages)
        if tail:
            chunks.append(tail)
    elif kind in ("thesis", "dissertation"):
        tail = _join([school, year])
        if tail:
            chunks.append(tail)
    elif kind == "standard":
        # 标准号已在 head 里（``GB/T 7714—2015 信息与文献…[S]``），这里只补出版项
        tail = _join([publisher, year])
        if tail:
            chunks.append(tail)
    elif kind in ("online", "electronic"):
        if date or cited:
            stamps: list[str] = []
            if date:
                stamps.append(f"({date})")
            if cited:
                stamps.append(f"[{cited}]")
            chunks.append("".join(stamps))
        if url:
            chunks.append(url)
    elif kind == "report":
        number_text = _text(entry.get("number"))
        pub_text = _join([publisher, year])
        tail = _join([number_text, pub_text])
        if tail:
            chunks.append(tail)
    else:  # misc / 其它：能拼多少拼多少
        tail = _join([year, place, publisher])
        if tail:
            chunks.append(tail)

    if doi:
        chunks.append(f"DOI: {doi}")
    if not chunks:
        return f"[{number}] 文献条目缺少字段"
    return ". ".join(chunks) + "."

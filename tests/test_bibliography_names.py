"""参考文献外文作者：``[bibliography] western_initials``。"""

from __future__ import annotations

from pathlib import Path

import pytest

from docgen.bibliography import (
    BibliographyPlan,
    _western_name,
    format_reference,
    plan_bibliography,
)
from docgen.config import Config, load_config
from docgen.errors import E_CONFIG, DocGenError
from docgen.parser.dfm import parse_dfm

BASE = 'config_version = "0.1"\n'

REFS = """\
[hewitt]
type = "article"
author = ["John A. Hewitt"]
title = "Technical services"
journal = "Library Journal"
year = "1983"
volume = "10"
issue = "2"
pages = "1-10"

[mixed]
type = "book"
author = ["Hewitt, Jane", "张三", "van der Waals J"]
title = "书名"
place = "北京"
publisher = "出版社"
year = "2020"
"""


def _refs(tmp_path: Path) -> Path:
    path = tmp_path / "refs.toml"
    path.write_text(REFS, encoding="utf-8")
    return path


def _config(tmp_path: Path, extra: str = "") -> Config:
    path = tmp_path / "c.toml"
    path.write_text(BASE + extra, encoding="utf-8")
    return load_config(path)


def _plan(
    tmp_path: Path, key: str, extra: str = "", refs: Path | None = None
) -> BibliographyPlan | None:
    return plan_bibliography(
        parse_dfm(f"引用[[cite:{key}]]。\n"),
        _config(tmp_path, extra),
        refs=refs or _refs(tmp_path),
    )


def test_western_name_forms() -> None:
    assert _western_name("John A. Hewitt") == "HEWITT J A"
    assert _western_name("Hewitt, John A.") == "HEWITT J A"
    assert _western_name("Hewitt J A") == "HEWITT J A"
    assert _western_name("Jean-Paul Sartre") == "SARTRE J P"
    assert _western_name("van der Waals J") == "VAN DER WAALS J"
    assert _western_name("John Smith Jr.") == "SMITH J Jr."


def test_western_name_keeps_cjk() -> None:
    assert _western_name("张三") == "张三"
    assert _western_name("李四") == "李四"


def test_western_initials_off_by_default(tmp_path: Path) -> None:
    plan = _plan(tmp_path, "hewitt")
    assert plan is not None
    assert plan.entries[0].startswith("[1] John A. Hewitt.")


def test_western_initials_apply(tmp_path: Path) -> None:
    plan = _plan(tmp_path, "hewitt", "\n[bibliography]\nwestern_initials = true\n")
    assert plan is not None
    assert plan.entries[0].startswith("[1] HEWITT J A.")


def test_western_initials_keep_cjk_and_normalize_others(tmp_path: Path) -> None:
    plan = _plan(tmp_path, "mixed", "\n[bibliography]\nwestern_initials = true\n")
    assert plan is not None
    assert plan.entries[0].startswith("[1] HEWITT J, 张三, VAN DER WAALS J.")


def test_western_initials_with_truncate(tmp_path: Path) -> None:
    refs = tmp_path / "r2.toml"
    refs.write_text(
        '[en4]\ntype = "article"\nauthor = ["Alpha A", "Beta B", "Gamma C", "Delta D"]\n'
        'title = "T"\njournal = "J"\nyear = "2020"\n',
        encoding="utf-8",
    )
    plan = _plan(
        tmp_path,
        "en4",
        "\n[bibliography]\nwestern_initials = true\nauthor_truncate = 3\n",
        refs=refs,
    )
    assert plan is not None
    assert plan.entries[0].startswith("[1] ALPHA A, BETA B, GAMMA C, et al.")


def test_western_initials_string_author(tmp_path: Path) -> None:
    refs = tmp_path / "r3.toml"
    refs.write_text(
        '[str]\ntype = "article"\nauthor = "John Smith"\ntitle = "T"\njournal = "J"\nyear = "2020"\n',
        encoding="utf-8",
    )
    plan = _plan(tmp_path, "str", "\n[bibliography]\nwestern_initials = true\n", refs=refs)
    assert plan is not None
    assert plan.entries[0].startswith("[1] SMITH J.")


def test_western_initials_invalid_value(tmp_path: Path) -> None:
    with pytest.raises(DocGenError) as error:
        _plan(tmp_path, "hewitt", '\n[bibliography]\nwestern_initials = "x"\n')
    assert error.value.code == E_CONFIG


def test_format_reference_accepts_option() -> None:
    text = format_reference(
        {"type": "article", "author": ["John Smith"], "title": "T"},
        1,
        western_initials=True,
    )
    assert text.startswith("SMITH J.")

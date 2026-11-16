"""目录级别：``[toc] levels`` → TOC 域 switch。"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from docgen.config import Config, load_config
from docgen.errors import DocGenError
from docgen.parser.dfm import parse_dfm
from docgen.render.docx import render_docx_bytes
from docgen.validate import validate_content

BASE = 'config_version = "0.1"\n'
DOC = "[[toc]]\n\n# 第一章\n\n## 1.1 小节\n\n### 1.1.1 子节\n"


def _config(tmp_path: Path, extra: str = "") -> Config:
    path = tmp_path / "c.toml"
    path.write_text(BASE + extra, encoding="utf-8")
    return load_config(path)


def _document(tmp_path: Path, extra: str = "", markdown: str = DOC) -> str:
    data = render_docx_bytes(parse_dfm(markdown), _config(tmp_path, extra), base_dir=tmp_path)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return archive.read("word/document.xml").decode("utf-8")


def _toc_instruction(document: str) -> str:
    import re

    match = re.search(r"TOC [^<]+", document)
    assert match is not None
    return match.group(0)


def test_default_toc_levels_1_to_9(tmp_path: Path) -> None:
    assert 'TOC \\o "1-9"' in _toc_instruction(_document(tmp_path))


@pytest.mark.parametrize(
    ("snippet", "expected"),
    [
        ("[toc]\nlevels = 3\n", 'TOC \\o "1-3"'),
        ("[toc]\nlevels = 2\n", 'TOC \\o "1-2"'),
        ('[toc]\nlevels = "2-4"\n', 'TOC \\o "2-4"'),
    ],
)
def test_toc_levels_config(tmp_path: Path, snippet: str, expected: str) -> None:
    document = _document(tmp_path, extra="\n" + snippet)
    assert expected in _toc_instruction(document)


@pytest.mark.parametrize("value", ["0", "10", "abc", "3-1", "1-10"])
def test_invalid_levels_raise(tmp_path: Path, value: str) -> None:
    extra = f'\n[toc]\nlevels = "{value}"\n'
    with pytest.raises(DocGenError) as caught:
        _document(tmp_path, extra=extra)
    assert caught.value.code == "E5001"


def test_invalid_levels_reported_by_validate(tmp_path: Path) -> None:
    errors = validate_content(
        parse_dfm("[[toc]]\n"),
        _config(tmp_path, '\n[toc]\nlevels = "0"\n'),
    )
    assert any(error.code == "E5001" for error in errors)


def test_toc_still_uses_word_field(tmp_path: Path) -> None:
    document = _document(tmp_path)
    assert "fldChar" in document
    assert "按 F9 更新目录" in document

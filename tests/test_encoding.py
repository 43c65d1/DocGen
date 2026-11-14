"""输入编码：UTF-8 优先、GB18030 兜底（不承诺覆盖所有编码）。"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from docgen.bibliography import load_references, plan_bibliography
from docgen.cli import main
from docgen.config import load_config
from docgen.encoding import decode_text
from docgen.errors import DocGenError
from docgen.parser.dfm import parse_dfm

BASE = 'config_version = "0.1"\n\n[math]\nengine = "plain"\n'


# --------------------------------------------------------------------------
# decode_text
# --------------------------------------------------------------------------
def test_utf8_plain() -> None:
    assert decode_text("正文".encode()) == "正文"


def test_utf8_bom() -> None:
    assert decode_text(b"\xef\xbb\xbf" + "正文".encode()) == "正文"


def test_gbk_fallback() -> None:
    assert decode_text("张三. 中文标题".encode("gbk")) == "张三. 中文标题"


def test_gb18030_fallback() -> None:
    text = "𠀀"  # 4 字节 GB18030
    assert decode_text(text.encode("gb18030")) == text


def test_undecodable_raises_with_tried_encodings() -> None:
    with pytest.raises(DocGenError) as caught:
        decode_text(b"\xff\xfe\x00bad", path="x.toml")
    assert caught.value.code == "E5001"
    assert "utf-8" in str(caught.value) and "gb18030" in str(caught.value)


# --------------------------------------------------------------------------
# DFM 源文件
# --------------------------------------------------------------------------
def _write(path: Path, text: str, encoding: str) -> Path:
    path.write_bytes(text.encode(encoding))
    return path


def test_build_gbk_source(tmp_path: Path) -> None:
    source = _write(tmp_path / "doc.md", "# 标题\n\n正文中文。\n", "gbk")
    config = _write(tmp_path / "c.toml", BASE, "gbk")
    out = tmp_path / "out.docx"
    assert main(["build", str(source), "-c", str(config), "-o", str(out)]) == 0
    with zipfile.ZipFile(out) as archive:
        document = archive.read("word/document.xml").decode("utf-8")
    assert "正文中文" in document


def test_build_gbk_source_dump_ir(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = _write(tmp_path / "doc.md", "中文段落。\n", "gbk")
    assert main(["dump-ir", str(source)]) == 0
    assert "中文段落" in capsys.readouterr().out


# --------------------------------------------------------------------------
# config
# --------------------------------------------------------------------------
def test_load_gbk_config(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "c.toml",
        BASE + '\n[document]\nfont.name = "宋体"\nfont.size = "12pt"\n',
        "gbk",
    )
    config = load_config(path)
    assert config.setting("font.name") == "宋体"


def test_load_utf8_bom_config(tmp_path: Path) -> None:
    path = tmp_path / "c.toml"
    path.write_bytes(b"\xef\xbb\xbf" + (BASE + '\n[document]\nfont.size = "12pt"\n').encode())
    config = load_config(path)
    assert config.setting("font.size") == "12pt"


# --------------------------------------------------------------------------
# 文献库
# --------------------------------------------------------------------------
REFS_ZH = (
    "[zhang2024]\n"
    'type = "article"\n'
    'author = ["张三"]\n'
    'title = "中文标题"\n'
    'journal = "期刊"\n'
    'year = "2024"\n'
)


def test_gbk_references_file(tmp_path: Path) -> None:
    refs = _write(tmp_path / "refs.toml", REFS_ZH, "gbk")
    references = load_references(refs)
    assert references["zhang2024"]["title"] == "中文标题"


def test_gbk_references_render(tmp_path: Path) -> None:
    refs = _write(tmp_path / "refs.toml", REFS_ZH, "gbk")
    config_path = _write(tmp_path / "c.toml", BASE, "gbk")
    source = _write(tmp_path / "doc.md", "引用[[cite:zhang2024]]。\n", "gbk")
    out = tmp_path / "out.docx"
    assert (
        main(["build", str(source), "-c", str(config_path), "--refs", str(refs), "-o", str(out)])
        == 0
    )
    with zipfile.ZipFile(out) as archive:
        document = archive.read("word/document.xml").decode("utf-8")
    assert "[1]" in document and "中文标题" in document


def test_bibliography_plan_with_gbk_refs(tmp_path: Path) -> None:
    refs = _write(tmp_path / "refs.toml", REFS_ZH, "gbk")
    blocks = parse_dfm("引用[[cite:zhang2024]]。\n")
    plan = plan_bibliography(
        blocks, load_config(_write(tmp_path / "c.toml", BASE, "gbk")), refs=refs
    )
    assert plan is not None and plan.entries[0].startswith("[1] 张三. 中文标题")

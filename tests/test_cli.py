"""CLI 契约（手册 §10）：子命令、stdout/stderr 与退出码。

退出码：0 成功；1 内容错误（DocGenError）；2 配置/文件错误。
"""

import json
from pathlib import Path

import pytest

from docgen import errors
from docgen.cli import main
from docgen.ir import BlockNode

FIXTURES = Path(__file__).parent / "fixtures"
CONFIG = str(FIXTURES / "minimal.toml")


def test_no_arguments_shows_usage_and_exits_2(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as caught:
        main([])
    assert caught.value.code == 2
    assert "usage" in capsys.readouterr().err


def test_dump_ir_succeeds_and_prints_ir(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["dump-ir", str(FIXTURES / "minimal.md")]) == 0
    out = capsys.readouterr().out
    assert "Heading(" in out
    assert "level=1" in out
    assert "source_line=1" in out
    assert "Paragraph(" in out


def test_dump_ir_missing_file_exits_2(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["dump-ir", "tests/fixtures/not-there.md"]) == 2
    captured = capsys.readouterr()
    assert errors.E_CONFIG in captured.err
    assert captured.out == ""


def test_dump_ir_rejects_non_utf8_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bad = tmp_path / "bad.md"
    bad.write_bytes(b"\xff\xfe# not utf-8\n")
    assert main(["dump-ir", str(bad)]) == 2
    assert errors.E_CONFIG in capsys.readouterr().err


def test_dump_ir_normalizes_input(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    crlf = tmp_path / "crlf.md"
    crlf.write_bytes("\ufeff# 标题\r\n\r\n正文\r\n".encode())
    assert main(["dump-ir", str(crlf)]) == 0
    out = capsys.readouterr().out
    assert "source_line=1" in out
    assert "source_line=3" in out


def test_dump_styles_outputs_resolved_values(capsys: pytest.CaptureFixture[str]) -> None:
    """fixture 里 body 用 @ref 指向 document：展开后必须看到实际值。"""
    assert main(["dump-styles", "-c", CONFIG]) == 0
    out = capsys.readouterr().out
    assert "[styles.heading1]" in out
    assert 'font_weight = "bold"' in out
    assert "[styles.body]" in out
    assert 'font_size = "16px"' in out  # @document.font_size 已解析

    from docgen.config import build_style_tree, load_config

    assert build_style_tree(load_config(Path(CONFIG)))["styles"]["body"] == {"font_size": "16px"}


def test_dump_styles_raw_keeps_references(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["dump-styles", "-c", CONFIG, "--raw"]) == 0
    out = capsys.readouterr().out
    assert 'font_size = "@document.font_size"' in out
    assert "[document]" in out


def test_dump_styles_missing_config_exits_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["dump-styles", "-c", str(tmp_path / "nope.toml")]) == 2
    assert "E5001" in capsys.readouterr().err


def test_check_ok_exits_0(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = tmp_path / "doc.md"
    source.write_text("# 标题\n\n正文\n", encoding="utf-8")
    assert main(["check", str(source), "-c", CONFIG]) == 0
    assert "OK" in capsys.readouterr().out


def test_check_reports_unknown_style_in_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "doc.md"
    source.write_text("正文\n\n[x]{.nope}\n", encoding="utf-8")
    assert main(["check", str(source), "-c", CONFIG, "--json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["errors"][0]["code"] == errors.E_UNKNOWN_STYLE
    assert payload["errors"][0]["line"] == 3
    assert payload["errors"][0]["file"] == str(source)


def test_check_reports_unknown_style_in_text(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "doc.md"
    source.write_text("[x]{.nope}\n", encoding="utf-8")
    assert main(["check", str(source), "-c", CONFIG]) == 1
    captured = capsys.readouterr()
    assert "E1003" in captured.err
    assert "nope" in captured.err
    assert captured.out == ""


def test_check_missing_config_exits_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = tmp_path / "doc.md"
    source.write_text("正文\n", encoding="utf-8")
    assert main(["check", str(source), "-c", str(tmp_path / "nope.toml")]) == 2
    assert "E5001" in capsys.readouterr().err


def test_build_writes_html_end_to_end(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = tmp_path / "doc.md"
    source.write_text("# 文档标题\n\n正文 **粗体**\n\n[[pagebreak]]\n", encoding="utf-8")
    output = tmp_path / "out.html"
    assert main(["build", str(source), "-c", CONFIG, "-o", str(output)]) == 0

    document = output.read_text(encoding="utf-8")
    assert document.startswith("<!DOCTYPE html>")
    assert "<title>文档标题</title>" in document
    assert "<h1" in document and "文档标题" in document
    assert "<strong" in document
    assert '<hr class="pagebreak">' in document
    assert "已生成" in capsys.readouterr().out


def test_build_reports_content_errors_and_writes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "doc.md"
    source.write_text("[x]{.nope}\n", encoding="utf-8")
    output = tmp_path / "out.html"
    assert main(["build", str(source), "-c", CONFIG, "-o", str(output)]) == 1
    assert not output.exists()
    assert "E1003" in capsys.readouterr().err


def test_build_missing_config_exits_2(tmp_path: Path) -> None:
    source = tmp_path / "doc.md"
    source.write_text("正文\n", encoding="utf-8")
    assert main(["build", str(source), "-c", str(tmp_path / "nope.toml")]) == 2


def test_build_defaults_config_next_to_source(tmp_path: Path) -> None:
    (tmp_path / "config.toml").write_text(
        'config_version = "0.1"\n\n[styles.a]\ncolor = "red"\n', encoding="utf-8"
    )
    source = tmp_path / "doc.md"
    source.write_text("# 标题\n", encoding="utf-8")
    output = tmp_path / "out.html"
    assert main(["build", str(source), "-o", str(output)]) == 0
    assert output.is_file()


def test_build_docx_by_extension_writes_word_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """完整版：-o 是 .docx 时自动走 Word 后端。"""
    source = tmp_path / "doc.md"
    source.write_text("# 标题\n\n正文 **粗体**\n", encoding="utf-8")
    output = tmp_path / "out.docx"
    assert main(["build", str(source), "-c", CONFIG, "-o", str(output)]) == 0
    assert output.is_file()
    assert output.read_bytes()[:2] == b"PK"  # docx 是 zip 包
    assert "docx" in capsys.readouterr().out


def test_build_docx_with_explicit_format(tmp_path: Path) -> None:
    source = tmp_path / "doc.md"
    source.write_text("# 标题\n", encoding="utf-8")
    output = tmp_path / "out.bin"  # 扩展名不可推断，靠 --format 指定
    assert main(["build", str(source), "-c", CONFIG, "-o", str(output), "--format", "docx"]) == 0
    assert output.read_bytes()[:2] == b"PK"


def test_build_html_format_still_works(tmp_path: Path) -> None:
    source = tmp_path / "doc.md"
    source.write_text("# 标题\n", encoding="utf-8")
    output = tmp_path / "out.html"
    assert main(["build", str(source), "-c", CONFIG, "-o", str(output)]) == 0
    assert output.read_text(encoding="utf-8").startswith("<!DOCTYPE html>")


def test_build_rejects_unknown_format(tmp_path: Path) -> None:
    source = tmp_path / "doc.md"
    source.write_text("# 标题\n", encoding="utf-8")
    with pytest.raises(SystemExit) as caught:
        main(["build", str(source), "-o", "out.pdf", "--format", "pdf"])
    assert caught.value.code == 2


def test_check_strict_reports_unclosed_marker_in_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "doc.md"
    source.write_text("正文\n\n[[img:a.png\n", encoding="utf-8")
    # 非严格模式：解析器宽容，没有语义错误
    assert main(["check", str(source), "-c", CONFIG]) == 0
    capsys.readouterr()
    # 严格模式：报未闭合标记
    assert main(["check", str(source), "-c", CONFIG, "--strict", "--json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["strict"] is True
    assert payload["errors"][0]["code"] == errors.E_UNCLOSED_MARKER
    assert payload["errors"][0]["line"] == 3
    assert payload["errors"][0]["file"] == str(source)


def test_check_strict_text_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = tmp_path / "doc.md"
    source.write_text("```cobol\nDISPLAY 'HI'.\n```\n", encoding="utf-8")
    assert main(["check", str(source), "-c", CONFIG, "--strict"]) == 1
    captured = capsys.readouterr()
    assert "E2001" in captured.err
    assert "cobol" in captured.err


def test_check_strict_passes_clean_document(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "pics").mkdir()
    (tmp_path / "pics" / "a.png").write_bytes(b"png")
    source = tmp_path / "doc.md"
    source.write_text(
        "# 标题\n\n[[img:pics/a.png]]\n\n```python\nprint(1)\n```\n", encoding="utf-8"
    )
    assert main(["check", str(source), "-c", CONFIG, "--strict"]) == 0
    assert "OK" in capsys.readouterr().out


def test_check_content_error_exits_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """内容错误走 DocGenError -> 退出码 1（配置/文件错误才是 2）。"""
    from docgen import cli

    def _boom(text: str) -> list[BlockNode]:
        raise errors.DocGenError(errors.E_SYNTAX, "解析失败")

    monkeypatch.setattr(cli, "parse_dfm", _boom)
    assert main(["dump-ir", str(FIXTURES / "minimal.md")]) == 1
    assert "E4001:解析失败" in capsys.readouterr().err

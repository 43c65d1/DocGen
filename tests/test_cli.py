"""CLI 契约（手册 §10）：子命令、stdout/stderr 与退出码。

退出码：0 成功；1 内容错误（DocGenError）；2 配置/文件错误。
"""

import argparse
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


# --------------------------------------------------------------------------
# `--help` 也是对外契约：它过时过——description 还写着「DFM + TOML -> HTML」，
# 而 Word 后端早就有了。用户是从 `--help` 认识这个工具的，所以在这里锁住内容。
#
# 注意断言要**足够强**：最初写的版本用 `"Word" in out`，结果被 epilog 示例里的
# `out.docx` 命中；检查参数说明用 `"config.toml" in out`，又被 `-c/--config`
# 自己的 help 命中——两条都抓不到回归（已用"故意删掉 help 再跑"验证过）。
# 所以改成直接检查 parser 结构。
# --------------------------------------------------------------------------
def _help_of(argv: list[str], monkeypatch: pytest.MonkeyPatch) -> str:
    """拿到 parser 生成的帮助文本（不依赖 capsys，可重复调用）。"""
    import io
    import sys

    buf = io.StringIO()
    monkeypatch.setattr(sys, "stdout", buf)
    with pytest.raises(SystemExit):
        main([*argv, "--help"])
    return buf.getvalue()


def test_root_help_mentions_both_backends(monkeypatch: pytest.MonkeyPatch) -> None:
    """`--help` 的**说明段**必须点明 HTML 和 Word 两个后端。"""
    out = _help_of([], monkeypatch)
    # 只看 usage 行之后、第一个小节之前的说明段（epilog 里的 out.docx 不算）
    description = out.split("usage:", 1)[1].split("\n\n", 1)[1].split("options:")[0]
    assert "HTML" in description and "Word" in description, (
        f"帮助说明段没提两个后端：{description!r}"
    )
    assert "docx" in description, "说明段应点出 docx"


def test_root_help_documents_exit_codes(monkeypatch: pytest.MonkeyPatch) -> None:
    """退出码是对外契约的一部分（脚本要按它判断），帮助里要说清。"""
    out = _help_of([], monkeypatch)
    assert "退出码" in out, "帮助里没有退出码说明"
    # 取「退出码」后面那一行来查数字——不能全文找，否则别的数字会误命中
    line = next(line for line in out.splitlines() if "退出码" in line)
    for code in ("0", "1", "2", "130"):
        assert code in line, f"退出码那一行没写 {code}：{line!r}"


def test_root_help_has_runnable_examples(monkeypatch: pytest.MonkeyPatch) -> None:
    """帮助里要给出可照抄的示例命令。"""
    out = _help_of([], monkeypatch)
    assert "示例" in out
    assert "docgen check" in out and "docgen build" in out


def _actions(parser: argparse.ArgumentParser) -> list[argparse.Action]:
    """展开一个 parser 的全部子 parser 与其 action。"""
    found: list[argparse.Action] = []
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for sub in action.choices.values():
                found.extend(sub._actions)
    return found


def test_every_argument_has_help_text() -> None:
    """每个参数都要有说明。

    实测：`dump-ir` / `dump-styles` / `check` / `bug-report` 的参数一度都没有 help，
    帮助里只剩光秃秃的 `positional arguments: input`，等于没写。
    这里直接查 parser 结构——比在帮助正文里找词可靠（找词会被别的 help 命中）。
    """
    from docgen.cli import _build_parser

    parser = _build_parser()
    missing: list[str] = []
    # `cmd` 是 subparsers 的 dest（不是用户直接传的参数），不需要 help
    skip = {"help", "cmd"}
    for action in parser._actions:
        if action.dest not in skip and not action.help:
            missing.append(f"全局 {action.dest}")
    for action in _actions(parser):
        if action.dest not in skip and not action.help:
            missing.append(str(action.dest))
    assert not missing, f"这些参数没有 help 说明：{missing}"


def test_subcommand_helps_describe_their_input() -> None:
    """子命令的参数说明要说到点子上（源文件 / config），不能敷衍。"""
    from docgen.cli import _build_parser

    parser = _build_parser()
    helps = {str(getattr(a, "dest", "")): (a.help or "") for a in _actions(parser)}
    assert "DFM" in helps["input"], "input 的说明应点明是 DFM 源文件"
    assert "config" in helps["config"].lower(), "config 的说明应点明是 config.toml"


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

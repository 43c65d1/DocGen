"""Output 系统契约（日志级别阈值 / 分流 / logfile / CLI 开关 / bug-report）。"""

from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest

from docgen import cli
from docgen.output import LEVELS, Output, parse_level


# --------------------------------------------------------------------------
# 级别：阈值语义
# --------------------------------------------------------------------------
def test_levels_are_ordered() -> None:
    assert LEVELS["log"] < LEVELS["warn"] < LEVELS["err"] < LEVELS["none"]


def test_parse_level_accepts_aliases() -> None:
    assert parse_level("WARN") == "warn"
    assert parse_level("warning") == "warn"
    assert parse_level("error") == "err"
    assert parse_level("off") == "none"
    assert parse_level("verbose") == "log"
    assert parse_level("nonsense", default="warn") == "warn"


def _sink() -> tuple[Output, io.StringIO, io.StringIO]:
    out, err = io.StringIO(), io.StringIO()
    return Output("warn", stdout=out, stderr=err), out, err


def test_warn_level_hides_log_but_keeps_warn_and_err() -> None:
    """级别是**阈值**：warn 时不打印 log，但 warn/err 照常。"""
    output, _, err = _sink()
    output.log("verbose only")
    output.warn("default visible")
    output.error("always visible")
    text = err.getvalue()
    assert "verbose only" not in text
    assert "[warn] default visible" in text
    assert "[err] always visible" in text


def test_log_level_shows_everything() -> None:
    output, _, err = _sink()
    output.level = "log"
    output.log("a")
    output.warn("b")
    output.error("c")
    assert err.getvalue().count("\n") == 3


def test_err_level_shows_only_errors() -> None:
    output, _, err = _sink()
    output.level = "err"
    output.log("a")
    output.warn("b")
    output.error("c")
    assert err.getvalue().strip() == "[err] c"


def test_none_level_is_silent() -> None:
    output, _, err = _sink()
    output.level = "none"
    output.log("a")
    output.warn("b")
    output.error("c")
    assert err.getvalue() == ""


def test_diagnostics_go_to_stderr_results_go_to_stdout() -> None:
    """分流：结果 stdout，诊断 stderr。"""
    output, out, err = _sink()
    output.results("RESULT")
    output.warn("DIAG")
    assert "RESULT" in out.getvalue()
    assert "RESULT" not in err.getvalue()
    assert "DIAG" in err.getvalue()
    assert "DIAG" not in out.getvalue()


def test_results_are_not_suppressed_by_level() -> None:
    """``-q``（err 阈值）只收诊断，**结果照常**——否则脚本拿不到输出。"""
    output, out, _ = _sink()
    output.level = "err"
    output.results("still here")
    assert "still here" in out.getvalue()


def test_none_level_silences_results_too() -> None:
    """``level = none`` 是**完全静默**（连结果一起），只保留退出码。"""
    output, out, err = _sink()
    output.level = "none"
    output.results("should not appear")
    output.warn("nor this")
    assert out.getvalue() == ""
    assert err.getvalue() == ""


def test_none_level_still_writes_logfile(tmp_path: Path) -> None:
    """静默只针对**终端**：文件日志按 logfile_level 照常记录。"""
    log = tmp_path / "run.log"
    output = Output("none", logfile=str(log), logfile_level="log")
    output.open_logfile(version="x")
    output.warn("file keeps it")
    output.close(exit_code=3)
    text = log.read_text(encoding="utf-8")
    assert "[warn] file keeps it" in text
    assert "exit code: 3" in text


def test_streams_are_resolved_lazily() -> None:
    """不显式传流时，运行期取 sys.stdout/stderr（否则 capsys 失效）。"""
    output = Output("log")
    assert output.stdout is sys.stdout
    assert output.stderr is sys.stderr


# --------------------------------------------------------------------------
# logfile
# --------------------------------------------------------------------------
def test_logfile_disabled_by_default(tmp_path: Path) -> None:
    output, _, _ = _sink()
    assert output.path is None
    assert output.open_logfile() is False


def test_logfile_header_and_footer(tmp_path: Path) -> None:
    log = tmp_path / "run.log"
    output = Output("warn", logfile=str(log))
    assert output.open_logfile(config_path="cfg.toml", input_path="in.md", version="1.2.3")
    output.warn("hello")
    output.close(exit_code=0, notes={"command": "build"})
    text = log.read_text(encoding="utf-8")
    for expected in (
        "docgen   : 1.2.3",
        "python   :",
        "platform :",
        "config   : cfg.toml",
        "input    : in.md",
        "exit code: 0",
        "command: build",
        "[warn] hello",
    ):
        assert expected in text, expected


def test_logfile_is_overwritten_not_appended(tmp_path: Path) -> None:
    log = tmp_path / "run.log"
    log.write_text("旧的垃圾内容\n" * 100, encoding="utf-8")
    output = Output("log", logfile=str(log))
    output.open_logfile(version="x")
    assert "旧的垃圾内容" not in log.read_text(encoding="utf-8")


def test_logfile_level_independent_of_terminal(tmp_path: Path) -> None:
    """终端 warn、文件 log：文件更详细（需求点名的用法）。"""
    log = tmp_path / "run.log"
    out, err = io.StringIO(), io.StringIO()
    output = Output("warn", logfile=str(log), logfile_level="log", stdout=out, stderr=err)
    output.open_logfile(version="x")
    output.log("detail-only-in-file")
    output.warn("both")
    output.close(exit_code=0)
    text = log.read_text(encoding="utf-8")
    assert "detail-only-in-file" in text  # 文件按 log 级
    assert "both" in text
    # 终端按 warn 级：log 级不上屏
    assert "detail-only-in-file" not in err.getvalue()
    assert "both" in err.getvalue()


def test_logfile_filters_by_its_own_level(tmp_path: Path) -> None:
    log = tmp_path / "run.log"
    output = Output("log", logfile=str(log), logfile_level="err")
    output.open_logfile(version="x")
    output.log("no")
    output.warn("no")
    output.error("yes")
    output.close(exit_code=0)
    text = log.read_text(encoding="utf-8")
    assert "[err] yes" in text
    assert "[warn] no" not in text


def test_logfile_survives_unwritable_path(tmp_path: Path) -> None:
    """日志写不进去不应让构建失败（静默降级）。"""
    output = Output("log", logfile=str(tmp_path / "no" / "such\x00" / "dir" / "x.log"))
    assert output.open_logfile() is False
    output.log("should not raise")


def test_secret_environment_is_filtered(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MY_API_TOKEN", "super-secret")
    monkeypatch.setenv("HARMLESS", "ok")
    log = tmp_path / "run.log"
    output = Output("log", logfile=str(log))
    output.open_logfile(version="x")
    text = log.read_text(encoding="utf-8")
    assert "super-secret" not in text
    assert "HARMLESS=ok" in text


# --------------------------------------------------------------------------
# CLI 集成
# --------------------------------------------------------------------------
CONFIG = """\
config_version = "0.1"

[table]
style = "three_line"
"""

BARE_CONFIG = 'config_version = "0.1"\n'


def _write(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_cli_quiet_keeps_results_but_hides_log(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = _write(tmp_path, "c.toml", CONFIG)
    source = _write(tmp_path, "a.md", "# 标题\n\n正文\n")
    cli.main(["-q", "build", str(source), "-c", str(config), "-o", str(tmp_path / "o.html")])
    captured = capsys.readouterr()
    assert "已生成" in captured.out  # 结果是结果，不被 quiet 吞
    assert "[warn]" not in captured.err


def test_cli_logfile_writes_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    config = _write(tmp_path, "c.toml", CONFIG)
    source = _write(tmp_path, "a.md", "# 标题\n")
    log = tmp_path / "run.log"
    code = cli.main(
        [
            "-v",
            "--logfile",
            str(log),
            "build",
            str(source),
            "-c",
            str(config),
            "-o",
            str(tmp_path / "o.html"),
        ]
    )
    assert code == 0
    text = log.read_text(encoding="utf-8")
    assert "exit code: 0" in text


def test_cli_output_config_level_none_is_silent_but_keeps_exit_code(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """``[output] level = none``：**完全静默**（连结果一起），**但退出码照常**。"""
    config = _write(tmp_path, "c.toml", BARE_CONFIG + '\n[output]\nlevel = "none"\n')
    bad = _write(tmp_path, "bad.md", "见 [x]{.nope}。\n")
    code = cli.main(["check", str(bad), "-c", str(config)])
    captured = capsys.readouterr()
    assert captured.err == ""  # 诊断静默
    assert captured.out == ""  # 结果也静默
    assert code == cli.EXIT_CONTENT_ERROR  # 退出码没有被静默


def test_cli_output_config_level_none_silences_success_too(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """成功时也静默（``check`` 不再打印 OK），退出码 0。"""
    config = _write(tmp_path, "c.toml", BARE_CONFIG + '\n[output]\nlevel = "none"\n')
    good = _write(tmp_path, "good.md", "正文\n")
    code = cli.main(["check", str(good), "-c", str(config)])
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""
    assert code == cli.EXIT_OK


def test_cli_output_config_logfile(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """``[output] logfile`` 让文件日志默认开启（无需命令行开关）。"""
    log = tmp_path / "from-config.log"
    config = _write(tmp_path, "c.toml", BARE_CONFIG + f'\n[output]\nlogfile = "{log.as_posix()}"\n')
    source = _write(tmp_path, "a.md", "正文\n")
    cli.main(["check", str(source), "-c", str(config)])
    assert log.is_file()
    assert "exit code: 0" in log.read_text(encoding="utf-8")


def test_cli_json_stdout_contains_only_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """``check --json`` 时 stdout 只有 JSON，诊断必须走 stderr。"""
    import json

    config = _write(tmp_path, "c.toml", CONFIG)
    source = _write(tmp_path, "a.md", "见 [x]{.nope}。\n")
    code = cli.main(["check", str(source), "-c", str(config), "--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)  # 解析失败就说明混进了别的东西
    assert payload["ok"] is False
    assert code == cli.EXIT_CONTENT_ERROR


def test_cli_quiet_logfile_still_verbose_in_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """``-q`` 只收终端；文件按 logfile_level 照常详细。"""
    log = tmp_path / "run.log"
    logline = f'\n[output]\nlogfile = "{log.as_posix()}"\nlogfile_level = "log"\n'
    config = _write(tmp_path, "c.toml", CONFIG + logline)
    source = _write(tmp_path, "a.md", "# 标题\n")
    cli.main(["-q", "build", str(source), "-c", str(config), "-o", str(tmp_path / "o.html")])
    assert log.is_file()


# --------------------------------------------------------------------------
# bug-report
# --------------------------------------------------------------------------
def test_bug_report_bundles_environment(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    config = _write(tmp_path, "c.toml", CONFIG)
    report = tmp_path / "report.txt"
    code = cli.main(["bug-report", "--output", str(report), "-c", str(config)])
    assert code == 0
    text = report.read_text(encoding="utf-8")
    for expected in (
        "=== docgen bug report ===",
        "docgen     :",
        "python     :",
        "platform   :",
        "环境变量",
        "config 摘要",
        "诊断",
    ):
        assert expected in text, expected
    assert "[code_block]" in text or "code_block" in text  # 展开了 config 摘要
    assert "已生成" in capsys.readouterr().out


def test_bug_report_filters_secrets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOME_PASSWORD", "leak-me")
    report = tmp_path / "r.txt"
    cli.main(["bug-report", "--output", str(report)])
    assert "leak-me" not in report.read_text(encoding="utf-8")

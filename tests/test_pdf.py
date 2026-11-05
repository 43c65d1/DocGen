"""docx → PDF 接口：引擎探测、参数优先级、错误码与 CLI 接线。"""

from __future__ import annotations

import types
from collections.abc import Callable
from pathlib import Path

import pytest

from docgen import pdf as pdfmod
from docgen.config import Config
from docgen.errors import DocGenError
from docgen.pdf import (
    PdfResult,
    build_word_script,
    convert,
    pdf_settings,
    resolve_engine,
    soffice_path,
    word_available,
)

BASE_CONFIG = 'config_version = "0.1"\n'


def _config(tmp_path: Path, extra: str = "") -> Config:
    from docgen.config import load_config

    path = tmp_path / "config.toml"
    path.write_text(BASE_CONFIG + extra, encoding="utf-8")
    return load_config(path)


# --------------------------------------------------------------------------
# 引擎探测
# --------------------------------------------------------------------------
def test_word_is_unavailable_off_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pdfmod, "os", types.SimpleNamespace(name="posix"))
    assert word_available() is False


def test_soffice_env_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fake = tmp_path / "soffice"
    fake.write_text("", encoding="utf-8")
    monkeypatch.setenv("DOCGEN_SOFFICE", str(fake))
    assert soffice_path() == str(fake)


def test_auto_prefers_word(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pdfmod, "word_available", lambda: True)
    monkeypatch.setattr(pdfmod, "soffice_path", lambda: "/usr/bin/soffice")
    assert resolve_engine("auto") == "word"


def test_auto_falls_back_to_libreoffice(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pdfmod, "word_available", lambda: False)
    monkeypatch.setattr(pdfmod, "soffice_path", lambda: "/usr/bin/soffice")
    assert resolve_engine("auto") == "libreoffice"


def test_auto_without_any_engine_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pdfmod, "word_available", lambda: False)
    monkeypatch.setattr(pdfmod, "soffice_path", lambda: None)
    with pytest.raises(DocGenError) as caught:
        resolve_engine("auto")
    assert caught.value.code == "E5005"
    assert "Microsoft Word" in str(caught.value)


def test_explicit_engine_unavailable_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pdfmod, "word_available", lambda: False)
    monkeypatch.setattr(pdfmod, "soffice_path", lambda: None)
    for engine in ("word", "libreoffice"):
        with pytest.raises(DocGenError) as caught:
            resolve_engine(engine)
        assert caught.value.code == "E5005"


def test_unknown_engine_is_config_error() -> None:
    with pytest.raises(DocGenError) as caught:
        resolve_engine("chrome")
    assert caught.value.code == "E5001"


# --------------------------------------------------------------------------
# Word 脚本
# --------------------------------------------------------------------------
def test_word_script_quotes_paths_and_exports_pdf(tmp_path: Path) -> None:
    source = tmp_path / "it's a doc.docx"
    target = tmp_path / "o'ut.pdf"
    script = build_word_script(source, target)
    assert "ExportAsFixedFormat" in script
    assert "17" in script  # wdExportFormatPDF
    assert "''" in script  # 单引号转义
    assert "Documents.Open" in script
    assert "Quit()" in script


# --------------------------------------------------------------------------
# convert()
# --------------------------------------------------------------------------
def _stub_engine(monkeypatch: pytest.MonkeyPatch, engine: str, *, produce: bool = True) -> None:
    monkeypatch.setattr(pdfmod, "resolve_engine", lambda requested: engine)

    def fake(source: Path, target: Path, timeout: float) -> None:
        if produce:
            target.write_bytes(b"%PDF-1.7 stub")

    monkeypatch.setattr(pdfmod, "_convert_with_word", fake)
    monkeypatch.setattr(pdfmod, "_convert_with_libreoffice", fake)


def test_convert_defaults_to_same_stem(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _stub_engine(monkeypatch, "word")
    docx = tmp_path / "report.docx"
    docx.write_bytes(b"docx")
    result = convert(docx)
    assert isinstance(result, PdfResult)
    assert result.path == (tmp_path / "report.pdf").resolve()
    assert result.engine == "word"
    assert result.path.read_bytes() == b"%PDF-1.7 stub"


def test_convert_creates_parent_and_overwrites(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _stub_engine(monkeypatch, "libreoffice")
    docx = tmp_path / "a.docx"
    docx.write_bytes(b"docx")
    target = tmp_path / "sub" / "dir" / "b.pdf"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"old")
    result = convert(docx, target)
    assert result.engine == "libreoffice"
    assert result.path.read_bytes().startswith(b"%PDF")


def test_convert_passes_absolute_paths_to_engine(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Word 按自己的进程工作目录解析相对路径——必须传绝对路径（实测踩到）。"""
    seen: dict[str, Path] = {}
    monkeypatch.setattr(pdfmod, "resolve_engine", lambda requested: "word")

    def fake(source: Path, target: Path, timeout: float) -> None:
        seen["source"] = source
        seen["target"] = target
        target.write_bytes(b"%PDF-1.7 stub")

    monkeypatch.setattr(pdfmod, "_convert_with_word", fake)
    docx = tmp_path / "relative.docx"
    docx.write_bytes(b"docx")
    convert(docx, tmp_path / "out" / "relative.pdf")
    assert seen["source"].is_absolute()
    assert seen["target"].is_absolute()


def test_convert_without_output_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _stub_engine(monkeypatch, "word", produce=False)
    docx = tmp_path / "a.docx"
    docx.write_bytes(b"docx")
    with pytest.raises(DocGenError) as caught:
        convert(docx)
    assert caught.value.code == "E5005"
    assert not (tmp_path / "a.pdf").exists()


def test_convert_missing_docx_raises(tmp_path: Path) -> None:
    with pytest.raises(DocGenError) as caught:
        convert(tmp_path / "missing.docx")
    assert caught.value.code == "E5005"


# --------------------------------------------------------------------------
# [pdf] 配置
# --------------------------------------------------------------------------
def test_pdf_settings_defaults(tmp_path: Path) -> None:
    assert pdf_settings(_config(tmp_path)) == (False, "auto", 120.0)


def test_pdf_settings_read_values(tmp_path: Path) -> None:
    config = _config(tmp_path, '[pdf]\nenabled = true\nengine = "libreoffice"\ntimeout = 30\n')
    assert pdf_settings(config) == (True, "libreoffice", 30.0)


def test_pdf_settings_reject_bad_values(tmp_path: Path) -> None:
    for extra in (
        '[pdf]\nenabled = "maybe"\n',
        '[pdf]\nengine = "chrome"\n',
        '[pdf]\ntimeout = "soon"\n',
        "[pdf]\ntimeout = 0\n",
    ):
        with pytest.raises(DocGenError) as caught:
            pdf_settings(_config(tmp_path, extra))
        assert caught.value.code == "E5001"


# --------------------------------------------------------------------------
# CLI 接线
# --------------------------------------------------------------------------
def _cli_fixture(tmp_path: Path, extra: str = "") -> tuple[Path, Path, Path]:
    source = tmp_path / "doc.md"
    source.write_text("# 标题\n\n正文。\n", encoding="utf-8")
    config = tmp_path / "c.toml"
    config.write_text(BASE_CONFIG + extra, encoding="utf-8")
    return source, config, tmp_path / "out.docx"


def _fake_convert(calls: list[dict[str, object]]) -> Callable[..., PdfResult]:
    def fake(docx: Path, pdf: Path, *, engine: str, timeout: float) -> PdfResult:
        calls.append({"docx": docx, "pdf": pdf, "engine": engine, "timeout": timeout})
        return PdfResult(path=pdf, engine="word" if engine == "auto" else engine)

    return fake


def test_cli_pdf_flag_converts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from docgen.cli import main

    source, config, output = _cli_fixture(tmp_path)
    calls: list[dict[str, object]] = []
    monkeypatch.setattr("docgen.pdf.convert", _fake_convert(calls))
    assert main(["build", str(source), "-c", str(config), "-o", str(output), "--pdf"]) == 0
    assert output.is_file(), "docx 仍应生成"
    assert len(calls) == 1
    assert calls[0]["pdf"] == output.with_suffix(".pdf")


def test_cli_pdf_engine_is_passed_through(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from docgen.cli import main

    source, config, output = _cli_fixture(tmp_path)
    calls: list[dict[str, object]] = []
    monkeypatch.setattr("docgen.pdf.convert", _fake_convert(calls))
    assert (
        main(
            [
                "build",
                str(source),
                "-c",
                str(config),
                "-o",
                str(output),
                "--pdf",
                "--pdf-engine",
                "libreoffice",
            ]
        )
        == 0
    )
    assert calls[0]["engine"] == "libreoffice"


def test_cli_config_enables_pdf(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from docgen.cli import main

    source, config, output = _cli_fixture(tmp_path, "[pdf]\nenabled = true\n")
    calls: list[dict[str, object]] = []
    monkeypatch.setattr("docgen.pdf.convert", _fake_convert(calls))
    assert main(["build", str(source), "-c", str(config), "-o", str(output)]) == 0
    assert len(calls) == 1


def test_cli_no_pdf_overrides_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from docgen.cli import main

    source, config, output = _cli_fixture(tmp_path, "[pdf]\nenabled = true\n")
    calls: list[dict[str, object]] = []
    monkeypatch.setattr("docgen.pdf.convert", _fake_convert(calls))
    assert main(["build", str(source), "-c", str(config), "-o", str(output), "--no-pdf"]) == 0
    assert calls == []


def test_cli_pdf_failure_keeps_docx_and_exit_3(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from docgen.cli import main

    source, config, output = _cli_fixture(tmp_path)

    def boom(*args: object, **kwargs: object) -> PdfResult:
        raise DocGenError("E5005", "模拟转换失败")

    monkeypatch.setattr("docgen.pdf.convert", boom)
    assert main(["build", str(source), "-c", str(config), "-o", str(output), "--pdf"]) == 3
    assert output.is_file(), "PDF 失败不能把已生成的 docx 一起丢掉"

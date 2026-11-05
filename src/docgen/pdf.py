"""docx → PDF（可选后处理）。

定位：**不改变渲染链路**——先产出 .docx（唯一真源），再交给外部引擎转 PDF。
所以 PDF 的排版结果等于该引擎自己的解释，DocGen 不保证两者逐像素一致。

两个引擎：

| engine | 依赖 | 特点 |
|---|---|---|
| ``word`` | Windows + 已装 Microsoft Word | **保真最高**：分页、字体、域都按 Word 计算 |
| ``libreoffice`` | ``soffice`` 可执行文件 | 跨平台；渲染细节与 Word 有差异（实测会忽略右页边距） |

``engine="auto"``：优先 ``word``，其次 ``libreoffice``；都没有就报 ``E5005``。

可用环境变量 ``DOCGEN_SOFFICE`` 指定 ``soffice`` 路径（系统不在 PATH 时用）。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import E_CONFIG, E_PDF, DocGenError

__all__ = [
    "ENGINES",
    "PdfResult",
    "available_engines",
    "build_word_script",
    "convert",
    "pdf_settings",
    "resolve_engine",
    "soffice_path",
    "word_available",
]

#: 可选的 PDF 引擎（``auto`` 自动挑）
ENGINES = ("auto", "word", "libreoffice")

#: Word 的 ``wdExportFormatPDF``（ExportAsFixedFormat 第二参数）
WD_EXPORT_FORMAT_PDF = 17


@dataclass(frozen=True, slots=True)
class PdfResult:
    """转换结果：目标路径 + 实际使用的引擎。"""

    path: Path
    engine: str


# --------------------------------------------------------------------------
# 引擎探测
# --------------------------------------------------------------------------
def word_available() -> bool:
    """本机是否能通过 COM 驱动 Word。

    用注册表 ``Word.Application`` 判断，而不是真的起一个 Word 进程——
    探测要快，且不应在每次 build 时启动 Office。
    """
    if os.name != "nt":
        return False
    try:
        import winreg
    except ImportError:  # pragma: no cover - 非 Windows 走不到
        return False
    try:
        key = winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "Word.Application")
    except OSError:
        return False
    winreg.CloseKey(key)
    return True


def soffice_path() -> str | None:
    """找 ``soffice``：``DOCGEN_SOFFICE`` → PATH → 常见安装位置。"""
    configured = os.environ.get("DOCGEN_SOFFICE", "").strip()
    if configured and Path(configured).is_file():
        return configured

    found = shutil.which("soffice") or shutil.which("libreoffice")
    if found:
        return found

    candidates: list[Path] = []
    if os.name == "nt":
        for base in (
            os.environ.get("ProgramFiles"),
            os.environ.get("ProgramFiles(x86)"),
            os.environ.get("LOCALAPPDATA", "")
            and str(Path(os.environ["LOCALAPPDATA"]) / "Programs"),
        ):
            if base:
                candidates.append(Path(base) / "LibreOffice" / "program" / "soffice.exe")
    elif sys.platform == "darwin":
        candidates.append(Path("/Applications/LibreOffice.app/Contents/MacOS/soffice"))
    else:
        candidates.extend(
            [
                Path("/usr/bin/soffice"),
                Path("/usr/lib/libreoffice/program/soffice"),
                Path("/snap/bin/libreoffice"),
            ]
        )
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return None


def available_engines() -> list[str]:
    """按优先级返回可用引擎。"""
    engines: list[str] = []
    if word_available():
        engines.append("word")
    if soffice_path():
        engines.append("libreoffice")
    return engines


def resolve_engine(engine: str) -> str:
    """把 ``auto`` 解析成具体引擎；不可用时给出可操作的错误信息。"""
    if engine not in ENGINES:
        raise DocGenError(
            E_CONFIG,
            f"[pdf] engine 不支持: {engine!r}（可用：{' / '.join(ENGINES)}）",
        )
    if engine == "auto":
        found = available_engines()
        if not found:
            raise DocGenError(
                E_PDF,
                "没有可用的 PDF 引擎：需要 Windows + Microsoft Word，"
                "或安装 LibreOffice 并确保 soffice 在 PATH（或用 DOCGEN_SOFFICE 指定路径）。",
            )
        return found[0]
    if engine == "word" and not word_available():
        raise DocGenError(E_PDF, "指定了 word 引擎，但本机没有可用的 Microsoft Word（COM）。")
    if engine == "libreoffice" and not soffice_path():
        raise DocGenError(
            E_PDF, "指定了 libreoffice 引擎，但找不到 soffice（可设置 DOCGEN_SOFFICE）。"
        )
    return engine


# --------------------------------------------------------------------------
# 配置
# --------------------------------------------------------------------------
def _as_bool(value: Any, label: str) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in ("true", "1", "yes", "on"):
        return True
    if text in ("false", "0", "no", "off"):
        return False
    raise DocGenError(E_CONFIG, f"{label} 需要 true/false，收到 {value!r}")


def pdf_settings(config: Any) -> tuple[bool, str, float]:
    """读 ``[pdf]`` 段：``(enabled, engine, timeout)``。

    ```toml
    [pdf]
    enabled = true          # build 时自动转 PDF（默认 false）
    engine = "auto"         # auto / word / libreoffice
    timeout = 120           # 秒
    ```
    """
    settings = config.namespace("pdf")
    if not settings:
        return False, "auto", 120.0

    enabled = _as_bool(settings.get("enabled", False), "[pdf] enabled")
    engine = str(settings.get("engine", "auto") or "auto").strip().lower()
    if engine not in ENGINES:
        raise DocGenError(
            E_CONFIG, f"[pdf] engine 不支持: {engine!r}（可用：{' / '.join(ENGINES)}）"
        )
    raw_timeout = settings.get("timeout", 120)
    try:
        timeout = float(raw_timeout)
    except (TypeError, ValueError):
        raise DocGenError(E_CONFIG, f"[pdf] timeout 需要数字（秒），收到 {raw_timeout!r}") from None
    if timeout <= 0:
        raise DocGenError(E_CONFIG, f"[pdf] timeout 必须为正数，收到 {raw_timeout!r}")
    return enabled, engine, timeout


# --------------------------------------------------------------------------
# 转换
# --------------------------------------------------------------------------
def convert(
    docx: Path,
    pdf: Path | None = None,
    *,
    engine: str = "auto",
    timeout: float = 120.0,
) -> PdfResult:
    """把 ``docx`` 转成 PDF，返回实际路径与所用引擎。

    ``pdf`` 省略时与 docx 同目录同名（``out.docx`` → ``out.pdf``）。
    失败抛 :class:`DocGenError`（``E5005``）；docx 本身不受影响。
    """
    source = Path(docx).resolve()
    if not source.is_file():
        raise DocGenError(E_PDF, f"要转换的 docx 不存在: {source}")

    target = Path(pdf) if pdf is not None else source.with_suffix(".pdf")
    # 必须用绝对路径：Word 的 COM 调用按 **Word 进程的工作目录**（常是
    # C:\WINDOWS\system32）解析相对路径，`docgen build -o t.docx --pdf`
    # 会因此报「找不到文件」（实测踩到）。
    target = target.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target.unlink()

    chosen = resolve_engine(engine)
    if chosen == "word":
        _convert_with_word(source, target, timeout)
    else:
        _convert_with_libreoffice(source, target, timeout)

    if not target.is_file() or target.stat().st_size == 0:
        raise DocGenError(E_PDF, f"{chosen} 引擎没有产出 PDF: {target}")
    return PdfResult(path=target, engine=chosen)


def _powershell() -> str:
    return shutil.which("pwsh") or shutil.which("powershell") or "powershell"


def _ps_quote(value: str | Path) -> str:
    """PowerShell 单引号字符串转义：内部单引号写两遍。"""
    return "'" + str(value).replace("'", "''") + "'"


def build_word_script(source: Path, target: Path) -> str:
    """生成 Word COM 导出脚本（独立函数便于测试；5.1/7 都能跑）。"""
    return (
        "$ErrorActionPreference = 'Stop'\n"
        "$word = New-Object -ComObject Word.Application\n"
        "$word.Visible = $false\n"
        "$word.DisplayAlerts = 0\n"
        "try {\n"
        f"    $doc = $word.Documents.Open({_ps_quote(source)}, $false, $true)\n"
        f"    $doc.ExportAsFixedFormat({_ps_quote(target)}, {WD_EXPORT_FORMAT_PDF})\n"
        "    $doc.Close($false)\n"
        "} finally {\n"
        "    $word.Quit()\n"
        "    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null\n"
        "}\n"
    )


def _convert_with_word(source: Path, target: Path, timeout: float) -> None:
    import tempfile as _tempfile

    script = build_word_script(source, target)
    with _tempfile.TemporaryDirectory(prefix="docgen-pdf-") as tmp:
        script_path = Path(tmp) / "word-to-pdf.ps1"
        # UTF-8 **带 BOM**：Windows PowerShell 5.1 才能正确读中文路径/中文注释
        script_path.write_text(script, encoding="utf-8-sig")
        try:
            result = subprocess.run(
                [
                    _powershell(),
                    "-NoProfile",
                    "-NonInteractive",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(script_path),
                ],
                capture_output=True,
                check=False,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            raise DocGenError(E_PDF, f"Word 转 PDF 超时（>{timeout:g} 秒）") from None
    if result.returncode != 0:
        detail = _tail(result.stderr or result.stdout)
        raise DocGenError(E_PDF, f"Word 转 PDF 失败：{detail}")


def _convert_with_libreoffice(source: Path, target: Path, timeout: float) -> None:
    executable = soffice_path()
    if executable is None:  # resolve_engine 已保证，防御一下
        raise DocGenError(E_PDF, "找不到 soffice")

    with tempfile.TemporaryDirectory(prefix="docgen-pdf-") as tmp:
        outdir = Path(tmp) / "out"
        profile = Path(tmp) / "profile"
        outdir.mkdir()
        profile.mkdir()
        command = [
            executable,
            "--headless",
            "--norestore",
            "--invisible",
            # 独立用户配置目录：避免与正在运行的 LibreOffice 抢锁
            f"-env:UserInstallation={profile.as_uri()}",
            "--convert-to",
            "pdf",
            "--outdir",
            str(outdir),
            str(source),
        ]
        try:
            result = subprocess.run(command, capture_output=True, check=False, timeout=timeout)
        except subprocess.TimeoutExpired:
            raise DocGenError(E_PDF, f"LibreOffice 转 PDF 超时（>{timeout:g} 秒）") from None
        produced = outdir / f"{source.stem}.pdf"
        if not produced.is_file():
            detail = _tail(result.stdout + result.stderr)
            raise DocGenError(E_PDF, f"LibreOffice 转 PDF 失败：{detail}")
        shutil.move(str(produced), str(target))


def _tail(raw: bytes) -> str:
    text = raw.decode("utf-8", "replace").strip()
    lines = [line for line in text.splitlines() if line.strip()]
    return " | ".join(lines[-3:])[:400] or "（无输出）"

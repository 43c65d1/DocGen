"""数学渲染：LaTeX → MathML → OMML（完整版手册 §4 / W2）。

链路：``latex2mathml`` 把 LaTeX 转成 MathML，再用 Office 的 **MML2OMML.XSL**
转成 OMML（``m:oMath``），插进 docx 的段落里——公式在 Word 里**可编辑**。

可配置（``[math]``）：

- ``engine``：``auto``（默认，按可用性挑）| ``xsl`` | ``plain``
- ``on_fail``：``error``（报 ``E5002``）| ``plain``（降级成 LaTeX 文本，默认）
- ``xsl``：显式指定 XSL 路径；也可用环境变量 ``DOCGEN_MML2OMML``

设计取舍：引擎可插拔、失败可观测。XSL 不是随处都有（Linux CI 通常没有），
所以默认 ``auto``：找不到 XSL 就用 ``plain``，保证构建不会因为公式挂掉。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..errors import E_MATH_CONVERSION, DocGenError

__all__ = [
    "MathResult",
    "available_engines",
    "find_xsl",
    "latex_to_omml",
    "math_settings",
]

#: 常见的 MML2OMML.XSL 位置（Windows 版 Office 随装；Linux/CI 通常没有）
XSL_CANDIDATES = (
    r"C:\Program Files\Microsoft Office\root\Office16\MML2OMML.XSL",
    r"C:\Program Files (x86)\Microsoft Office\root\Office16\MML2OMML.XSL",
    r"C:\Program Files\Microsoft Office\Office16\MML2OMML.XSL",
    "/usr/share/libreoffice/share/xslt/MML2OMML.XSL",
    "/usr/lib/libreoffice/share/xslt/MML2OMML.XSL",
)

#: XML 命名空间
MATHML_NS = "http://www.w3.org/1998/Math/MathML"
OMML_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"

_xsl_cache: dict[str, Any] = {}


@dataclass(frozen=True)
class MathResult:
    """一次数学转换的结果。"""

    omml: str | None
    engine: str
    latex: str
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.omml is not None


def find_xsl(explicit: str | Path | None = None) -> Path | None:
    """按 显式路径 → 环境变量 → 常见安装位置 的顺序找 MML2OMML.XSL。"""
    if explicit:
        candidate = Path(explicit)
        return candidate if candidate.is_file() else None
    from_env = os.environ.get("DOCGEN_MML2OMML")
    if from_env:
        candidate = Path(from_env)
        return candidate if candidate.is_file() else None
    for raw in XSL_CANDIDATES:
        candidate = Path(raw)
        if candidate.is_file():
            return candidate
    return None


def available_engines(xsl_path: str | Path | None = None) -> list[str]:
    """当前环境可用的数学引擎（按优先级）。"""
    engines: list[str] = []
    if find_xsl(xsl_path) is not None:
        engines.append("xsl")
    engines.append("plain")
    return engines


def math_settings(config: Any) -> tuple[str, str, str | None]:
    """从 config 读 ``[math]``：返回 ``(engine, on_fail, xsl)``。"""
    table = getattr(config, "raw", {}).get("math", {})
    if not isinstance(table, dict):
        table = {}
    engine = str(table.get("engine", "auto")).lower()
    on_fail = str(table.get("on_fail", "plain")).lower()
    xsl = table.get("xsl")
    return engine, on_fail, str(xsl) if xsl else None


def latex_to_omml(
    latex: str,
    *,
    engine: str = "auto",
    on_fail: str = "plain",
    xsl_path: str | Path | None = None,
) -> MathResult:
    """把一段 LaTeX 转成 OMML 字符串。

    - 成功：``MathResult(omml=..., engine="xsl")``
    - ``engine="plain"`` 或没有 XSL：``omml=None, engine="plain"``（调用方降级渲染）
    - ``on_fail="error"`` 且转换失败：抛 ``E5002``
    """
    if engine in ("plain", "none"):
        return MathResult(omml=None, engine="plain", latex=latex)

    path = find_xsl(xsl_path)
    if path is None:
        if on_fail == "error":
            raise DocGenError(E_MATH_CONVERSION, f"找不到 MML2OMML.XSL，无法转换公式: {latex}")
        return MathResult(omml=None, engine="plain", latex=latex, error="缺少 MML2OMML.XSL")

    try:
        omml = _transform(latex, path)
    except Exception as exc:  # noqa: BLE001 - 转换库异常类型不稳定，统一按失败处理
        # 有些异常（如 latex2mathml 的 NoAvailableTokensError）str() 为空，
        # 所以错误信息要用类型名兜底，否则失败会「静默无原因」
        detail = str(exc) or type(exc).__name__
        if on_fail == "error":
            raise DocGenError(E_MATH_CONVERSION, f"公式转换失败: {latex}: {detail}") from None
        return MathResult(omml=None, engine="plain", latex=latex, error=detail)

    if not omml:
        if on_fail == "error":
            raise DocGenError(E_MATH_CONVERSION, f"公式转换结果为空: {latex}")
        return MathResult(omml=None, engine="plain", latex=latex, error="转换结果为空")
    return MathResult(omml=omml, engine="xsl", latex=latex)


def _transform(latex: str, xsl_path: Path) -> str:
    """LaTeX -> MathML -> OMML（XSL 编译结果按路径缓存）。"""
    from latex2mathml.converter import convert
    from lxml import etree

    key = str(xsl_path)
    transform = _xsl_cache.get(key)
    if transform is None:
        transform = etree.XSLT(etree.parse(key))
        _xsl_cache[key] = transform

    mathml = convert(latex)
    if not mathml:
        # latex2mathml 对非法输入会返回空串而不是抛异常，这里统一成异常
        raise ValueError(f"latex2mathml 无法转换: {latex!r}")
    root = etree.fromstring(mathml)
    result = transform(root)
    text = str(result)
    # XSL 会带上 XML 声明与 m:oMath 外层，调用方只需要片段
    if "<?xml" in text:
        text = text.split("?>", 1)[1]
    return text.strip()


def omml_fragment(omml: str) -> str:
    """去掉命名空间前缀冲突风险：保留 ``m:`` 前缀并保证 xmlns 声明存在。"""
    if "xmlns:m=" in omml:
        return omml
    return omml.replace("<m:oMath", f'<m:oMath xmlns:m="{OMML_NS}"', 1)

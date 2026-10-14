"""数学渲染契约（完整版手册 §4 / W2）。

- ``latex2mathml`` → MathML → Office ``MML2OMML.XSL`` → OMML（``m:oMath``）
- 引擎可插拔、失败可观测（``on_fail = error | plain``）
- 测试集覆盖常见公式；统计转换通率（手册验收：> 90%）
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

import pytest

from docgen import errors
from docgen.render.math import (
    MathResult,
    available_engines,
    find_xsl,
    latex_to_omml,
    math_settings,
)

HAS_XSL = find_xsl() is not None
requires_xsl = pytest.mark.skipif(not HAS_XSL, reason="本机没有 MML2OMML.XSL（Office/LibreOffice）")

#: 覆盖常见排版的公式测试集（手册要求 30~50 条）
FORMULAS: tuple[str, ...] = (
    r"x^2",
    r"a + b = c",
    r"\frac{1}{2}",
    r"\frac{a+b}{c-d}",
    r"\sqrt{2}",
    r"\sqrt[3]{x}",
    r"\alpha + \beta = \gamma",
    r"\sum_{i=1}^{n} i^2",
    r"\int_0^1 x \, dx",
    r"\prod_{k=1}^{m} k",
    r"\lim_{x \to 0} \frac{\sin x}{x}",
    r"e^{i\pi} + 1 = 0",
    r"\log_2 n",
    r"O(n \log n)",
    r"x \in \mathbb{R}",
    r"a \le b \ge c \ne d",
    r"\vec{v} \cdot \vec{w}",
    r"\nabla f(x)",
    r"\partial_t u = \Delta u",
    r"\binom{n}{k}",
    r"\left( \frac{a}{b} \right)",
    r"\begin{matrix} a & b \\ c & d \end{matrix}",
    r"f(x) = \begin{cases} 1 & x > 0 \\ 0 & x \le 0 \end{cases}",
    r"\theta_{i,j}",
    r"x_{n+1}",
    r"\hat{y} = W x + b",
    r"\mathbb{E}[X]",
    r"\overline{AB}",
    r"\int_{-\infty}^{+\infty} e^{-x^2} dx = \sqrt{\pi}",
    r"\frac{\partial^2 f}{\partial x \partial y}",
    r"A \cup B \cap C",
    r"\forall x \exists y",
    r"a \equiv b \pmod n",
    r"\sin^2 \theta + \cos^2 \theta = 1",
    r"\sum_{\substack{i=1 \\ i \ne j}}^{n} a_i",
    r"\underbrace{a + b}_{m}",
    r"\mathcal{L}(f)",
    r"\tau \approx 3.14",
    r"\frac{d}{dx} \left( \int_a^x f(t) dt \right) = f(x)",
    r"F(x) = \int_{-\infty}^{x} f(t)\,dt",
)


def test_find_xsl_accepts_explicit_path(tmp_path: Path) -> None:
    xsl = tmp_path / "MML2OMML.XSL"
    xsl.write_text("<xsl:stylesheet/>", encoding="utf-8")
    assert find_xsl(xsl) == xsl


def test_find_xsl_returns_none_for_missing_path(tmp_path: Path) -> None:
    assert find_xsl(tmp_path / "nope.xsl") is None


def test_available_engines_always_includes_plain() -> None:
    assert "plain" in available_engines()


def test_math_settings_defaults() -> None:
    class _Config:
        raw: ClassVar[dict[str, object]] = {}

    assert math_settings(_Config()) == ("auto", "plain", None)


def test_math_settings_reads_config() -> None:
    class _Config:
        raw: ClassVar[dict[str, object]] = {
            "math": {"engine": "xsl", "on_fail": "error", "xsl": "C:/x.xsl"}
        }

    assert math_settings(_Config()) == ("xsl", "error", "C:/x.xsl")


def test_plain_engine_returns_no_omml() -> None:
    result = latex_to_omml(r"x^2", engine="plain")
    assert result == MathResult(omml=None, engine="plain", latex=r"x^2")
    assert result.ok is False


def test_missing_xsl_with_plain_fallback_is_not_an_error(tmp_path: Path) -> None:
    result = latex_to_omml("x", engine="xsl", xsl_path=tmp_path / "none.xsl")
    assert result.ok is False
    assert result.error


def test_missing_xsl_with_error_mode_raises(tmp_path: Path) -> None:
    with pytest.raises(errors.DocGenError) as caught:
        latex_to_omml("x", engine="xsl", on_fail="error", xsl_path=tmp_path / "none.xsl")
    assert caught.value.code == errors.E_MATH_CONVERSION


@requires_xsl
def test_simple_formula_produces_omml() -> None:
    result = latex_to_omml(r"x^2")
    assert result.ok is True
    assert result.engine == "xsl"
    assert "<m:oMath" in (result.omml or "")
    assert "<m:t>x</m:t>" in (result.omml or "")


@requires_xsl
def test_fraction_and_greek() -> None:
    result = latex_to_omml(r"\frac{\alpha}{\beta}")
    assert result.ok is True
    assert "<m:f>" in (result.omml or "")
    assert "α" in (result.omml or "")


@requires_xsl
def test_sum_and_integral() -> None:
    assert "<m:nary>" in (latex_to_omml(r"\sum_{i=1}^{n} i").omml or "")
    assert "<m:nary>" in (latex_to_omml(r"\int_0^1 x dx").omml or "")


@requires_xsl
def test_sqrt() -> None:
    assert "<m:rad>" in (latex_to_omml(r"\sqrt{2}").omml or "")


@requires_xsl
def test_conversion_rate_meets_target() -> None:
    """手册验收：公式转换通率 > 90%。"""
    ok = [latex for latex in FORMULAS if latex_to_omml(latex).ok]
    rate = len(ok) / len(FORMULAS)
    failed = [latex for latex in FORMULAS if latex not in ok]
    assert rate > 0.9, f"通率 {rate:.0%}，失败: {failed}"


@requires_xsl
def test_conversion_is_deterministic() -> None:
    first = latex_to_omml(r"\frac{1}{2} x^2")
    second = latex_to_omml(r"\frac{1}{2} x^2")
    assert first.omml == second.omml


@requires_xsl
def test_omml_is_valid_xml() -> None:
    from lxml import etree

    omml = latex_to_omml(r"\frac{a}{b}").omml
    assert omml
    root = etree.fromstring(omml.encode("utf-8"))
    assert root.tag.endswith("}oMath")


@requires_xsl
def test_bad_latex_falls_back_to_plain() -> None:
    result = latex_to_omml(r"\frac{1}{")
    if not result.ok:
        assert result.engine == "plain"
        assert result.error


@requires_xsl
def test_bad_latex_with_error_mode_raises() -> None:
    with pytest.raises(errors.DocGenError) as caught:
        latex_to_omml(r"\frac{1}{", on_fail="error")
    assert caught.value.code == errors.E_MATH_CONVERSION

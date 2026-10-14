"""发布物一致性：版本单一真源、三份文档存在、打包脚本可读。

这些是「测试版」的验收项——文件挪走了或版本漂移了，这里先红。
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Any

import pytest

from docgen.cli import VERSION, version_string

ROOT = Path(__file__).resolve().parents[1]


def _pyproject() -> dict[str, Any]:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def test_version_matches_pyproject() -> None:
    """``cli.VERSION`` 是兜底值，必须与 ``pyproject.toml`` 一致。

    漂移了就会出现「日志写 0.1.0、pip 元数据写 0.1.0b1」这种自相矛盾。
    """
    assert VERSION == _pyproject()["project"]["version"]


def test_version_string_is_non_empty() -> None:
    """装了包走元数据、没装走兜底，两种情况都不能是空串。"""
    assert version_string()
    assert isinstance(version_string(), str)


def test_version_looks_like_pep440() -> None:
    value = _pyproject()["project"]["version"]
    assert re.fullmatch(r"\d+\.\d+\.\d+(?:[ab]\d+|\.dev\d+|rc\d+)?", value), value


def test_lockfile_version_matches_pyproject() -> None:
    """``uv.lock`` 里 docgen 自身的版本也要同步。

    **注意不要用镜像去 `uv lock`**：那会把锁文件里 500+ 处 URL 全部改成镜像地址
    （实测踩到，已回滚）。改版本时手工改这一行即可——``uv sync`` 认它。
    """
    lock = (ROOT / "uv.lock").read_text(encoding="utf-8")
    match = re.search(r'\[\[package\]\]\nname = "docgen"\nversion = "([^"]+)"', lock)
    assert match is not None, "uv.lock 里找不到 docgen 条目"
    assert match.group(1) == _pyproject()["project"]["version"]


def test_lockfile_has_no_vendor_mirror_urls() -> None:
    """锁文件里不能出现国内镜像地址，否则别人 clone 后会指向我们的镜像。"""
    lock = (ROOT / "uv.lock").read_text(encoding="utf-8")
    for mirror in ("tuna.tsinghua", "aliyun", "douban", "mirrors.cloud"):
        assert mirror not in lock, f"锁文件被 {mirror} 污染了"


@pytest.mark.parametrize(
    "name", ["QUICKSTART.md", "LIMITATIONS.md", "FEEDBACK.md", "CHANGELOG.md", "README.md"]
)
def test_release_documents_exist(name: str) -> None:
    """发布测试版必须带的三份文档（外加 README/CHANGELOG）不能缺。"""
    path = ROOT / name
    assert path.is_file(), f"缺少发布文档: {name}"
    assert path.stat().st_size > 500, f"{name} 内容过少，像是空壳"


def test_development_manual_is_not_in_tmp() -> None:
    """手册曾被放在临时目录 ``.tmp/`` 里（随时会被清掉），现已转正到 docs/。"""
    assert (ROOT / "docs" / "development-manual.md").is_file()
    assert not (ROOT / ".tmp" / "DocGen(Hard-Version)开发手册.md").exists()


def test_package_script_exists_and_mentions_archive() -> None:
    script = ROOT / "scripts" / "package.sh"
    assert script.is_file()
    text = script.read_text(encoding="utf-8")
    assert "tar" in text and "zip" in text


@pytest.mark.parametrize(
    "name", ["QUICKSTART.md", "LIMITATIONS.md", "FEEDBACK.md", "CHANGELOG.md", "README.md"]
)
def test_package_script_ships_every_release_document(name: str) -> None:
    """打包脚本的清单必须覆盖全部发布文档。

    这条是**实测补的**：首次打包漏了 FEEDBACK.md，解压后跑本文件才失败——
    而那时包已经发出去了。清单与文档列表在这里对齐。
    """
    text = (ROOT / "scripts" / "package.sh").read_text(encoding="utf-8")
    assert name in text, f"package.sh 没有把 {name} 打进包"


def test_package_script_excludes_build_artifacts() -> None:
    """示例产物/缓存不该进包（跑一次就重新生成，白占体积）。"""
    text = (ROOT / "scripts" / "package.sh").read_text(encoding="utf-8")
    assert "output.html" in text and "output.docx" in text
    assert "__pycache__" in text


def test_setup_script_tries_multiple_sources() -> None:
    """装依赖脚本必须**尝试多个来源**，不能把某一个源写死。

    内外网状态会随时间变化：同一索引在不同网络下可能可用性不同。
    把某次探测结果固化成「唯一正确命令」，过几天就会失效。
    """
    text = (ROOT / "scripts" / "setup.sh").read_text(encoding="utf-8")
    assert '"$UV" sync' in text, "应该真的执行同步（通过 $UV 调用）"
    # 三种候选都要在：镜像、PyPI、代理
    assert "tsinghua" in text
    assert "pypi.org" in text
    assert "127.0.0.1:7897" in text
    # 支持手动指定，避免候选都不适用时无路可走
    assert "--index" in text and "--proxy" in text
    # 候选清单 + 逐个尝试（成功即停）
    assert "candidate" in text
    assert "try " in text and "&& exit 0" in text
    # 每个候选的可用性靠**真实同步**判断，不是靠预设结论
    assert "http_proxy=" in text  # 代理只是候选之一
    assert "UV_DEFAULT_INDEX" in text  # 索引可切换


def test_setup_script_has_a_no_proxy_path() -> None:
    """必须存在「不带代理、不带自定义索引」的尝试路径——否则等于把源写死。"""
    lines = (ROOT / "scripts" / "setup.sh").read_text(encoding="utf-8").splitlines()
    bare = [line for line in lines if '"$UV" sync $extra' in line and "http_proxy" not in line]
    assert bare, "找不到任何不带代理的同步调用（等于强制走代理）"
    # 该调用所在的 try 分支必须能传空 proxy（看调用点是否被 if 包着，靠候选表保证）
    assert any("|https://" in line for line in lines), "候选表里应含不带代理的条目"


def test_setup_script_does_not_hardcode_one_conclusion() -> None:
    """脚本注释/输出里不该出现「某源一定不可用」这类会过期的绝对结论。"""
    text = (ROOT / "scripts" / "setup.sh").read_text(encoding="utf-8")
    for absolute in ("一定超时", "必然失败", "永远不可用"):
        assert absolute not in text, absolute


def _git_bash() -> str | None:
    """找一个**真能跑 Windows 路径**的 bash。

    注意：Windows 上 `bash` 往往是 WSL 的 bash，它读不了 `C:\\...` 路径
    （`bash -n scripts/x.sh` 会失败）——实测踩到，所以这里优先找 Git Bash。
    """
    import shutil

    for candidate in (
        r"C:\Program Files\Git\bin\bash.exe",
        r"C:\Program Files\Git\usr\bin\bash.exe",
        r"C:\Program Files (x86)\Git\bin\bash.exe",
    ):
        if Path(candidate).is_file():
            return candidate
    return shutil.which("bash")


def test_shell_scripts_are_valid_bash() -> None:
    """语法检查：两个脚本要能被 bash 解析。"""
    import subprocess

    bash = _git_bash()
    if bash is None:  # pragma: no cover - 无 bash 的环境
        pytest.skip("环境里没有可用的 bash")
    for name in ("setup.sh", "package.sh"):
        result = subprocess.run(
            [bash, "-n", str(ROOT / "scripts" / name)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, f"{name} 语法错误: {result.stderr}"


def test_ci_workflow_is_tracked_in_repo() -> None:
    """CI 配置必须真实存在于工作区（曾出现「写了但忘了提交」）。"""
    workflow = ROOT / ".github" / "workflows" / "ci.yml"
    assert workflow.is_file()
    text = workflow.read_text(encoding="utf-8")
    for step in ("ruff check", "ruff format --check", "mypy", "pytest"):
        assert step in text, step


def test_manual_excluded_from_ruff_format() -> None:
    """手册含契约代码，必须从 ruff format 里排除，否则 CI 的 --check 会失败。"""
    config = _pyproject()["tool"]["ruff"]
    exclusions = config["exclude"]
    joined = " ".join(exclusions) if isinstance(exclusions, list) else str(exclusions)
    assert "development-manual" in joined


def test_limitations_cover_documented_design_limits() -> None:
    """限制清单要覆盖几个最容易被误报的设计边界。"""
    text = (ROOT / "LIMITATIONS.md").read_text(encoding="utf-8")
    for topic in ("three_line", "heading_numbering", "heading_indent", "font_weight", "none"):
        assert topic in text, f"限制清单漏了 {topic}"


def test_quickstart_references_key_commands() -> None:
    text = (ROOT / "QUICKSTART.md").read_text(encoding="utf-8")
    for command in (
        "docgen check",
        "docgen build",
        "docgen dump-ir",
        "docgen dump-styles",
        "docgen bug-report",
    ):
        assert command in text, command


def test_feedback_template_has_sections() -> None:
    text = (ROOT / "FEEDBACK.md").read_text(encoding="utf-8")
    for section in ("我做了什么", "期望", "环境", "bug-report"):
        assert section in text, section

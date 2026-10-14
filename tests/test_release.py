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
    "name",
    ["QUICKSTART.md", "LIMITATIONS.md", "FEEDBACK.md", "BRANCHING.md", "CHANGELOG.md", "README.md"],
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
    "name",
    ["QUICKSTART.md", "LIMITATIONS.md", "FEEDBACK.md", "BRANCHING.md", "CHANGELOG.md", "README.md"],
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


def test_setup_script_does_not_mutate_lockfile() -> None:
    """同步必须带 ``--frozen``，否则换个源就会把 ``uv.lock`` 里的 URL 全改掉。

    实测：用镜像跑一次不带 ``--frozen`` 的 ``uv sync``，锁文件里 500+ 处 URL
    会变成镜像地址；谁再提交一次就把镜像带进仓库了。
    ``--frozen`` 仍然按 ``--index`` 去镜像下载，只是不改锁文件。
    """
    text = (ROOT / "scripts" / "setup.sh").read_text(encoding="utf-8")
    sync_lines = [line for line in text.splitlines() if '"$UV" sync' in line]
    assert sync_lines, "找不到同步命令"
    for line in sync_lines:
        assert "--frozen" in line, f"这条同步没带 --frozen: {line.strip()}"


def test_quickstart_mentions_frozen() -> None:
    """文档要提醒手动同步时也加 ``--frozen``（否则锁文件会被源改写）。"""
    text = (ROOT / "QUICKSTART.md").read_text(encoding="utf-8")
    assert "--frozen" in text


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
    bare = [line for line in lines if '"$UV" sync' in line and "http_proxy" not in line]
    assert bare, "找不到任何不带代理的同步调用（等于强制走代理）"
    assert any("http_proxy=" in line and '"$UV" sync' in line for line in lines), (
        "也应该有带代理的同步调用（否则代理这条候选等于没实现）"
    )
    # 候选表里要有不带代理的条目
    assert any("|https://" in line for line in lines), "候选表里应含不带代理的条目"


def test_setup_script_does_not_hardcode_one_conclusion() -> None:
    """脚本注释/输出里不该出现「某源一定不可用」这类会过期的绝对结论。"""
    text = (ROOT / "scripts" / "setup.sh").read_text(encoding="utf-8")
    for absolute in ("一定超时", "必然失败", "永远不可用"):
        assert absolute not in text, absolute


def test_readme_directory_map_matches_source_tree() -> None:
    """README 的目录结构里点名的每个模块都必须真实存在。

    这条是**实际踩到后补的**：README 的目录树一度还停在早期版本，
    只列了部分模块、完全没提 Word 后端与后来新增的文件。
    """
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    block = re.search(r"## 目录结构.*?```\n(.*?)```", readme, re.DOTALL)
    assert block is not None, "README 里找不到目录结构代码块"
    tree = block.group(1)
    # 只取 src/docgen/ 那一段（到 tests/ 之前），避免把 tests 文件名与注释里的名字算进来
    source_section = tree.split("tests/")[0].split("src/docgen/")[-1]
    listed = set(re.findall(r"^\s*([a-z_]+\.py)\s", source_section, re.MULTILINE))
    assert listed, "目录结构里没列出任何 .py 模块"
    actual = {path.name for path in (ROOT / "src" / "docgen").rglob("*.py")}
    missing = {name for name in listed if name not in actual}
    assert not missing, f"README 列了不存在的模块: {sorted(missing)}"
    # 反向：核心模块不能漏（漏了就说明目录树过期了）
    for core in ("cli.py", "output.py", "config.py", "ir.py", "validate.py", "docx.py", "ooxml.py"):
        assert core in listed, f"README 目录结构漏了核心模块 {core}"


def test_readme_mentions_shipped_documents() -> None:
    """面向使用者的四份文档必须能从 README 找到入口。"""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for name in ("QUICKSTART.md", "LIMITATIONS.md", "FEEDBACK.md", "BRANCHING.md"):
        assert name in readme, f"README 没有链接 {name}"


def test_readme_describes_current_backends() -> None:
    """README 必须同时描述两个后端——不能退回只讲 HTML 的旧版本。"""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert ".docx" in readme and ".html" in readme
    assert "ECMA-376" in readme, "应说明产出过官方 schema 校验"
    # 不该再把"剪枝版"当成项目现状的主标题
    assert not readme.startswith("# DocGen（剪枝版"), "标题还在用剪枝版的旧定位"


def test_limitations_does_not_claim_unimplemented_for_shipped_feature() -> None:
    """限制清单不能把**已实现**的功能写成"无/不支持"。

    实测踩到：`[[toc]]` 早就能渲染成 Word 的 TOC 域（`_render_toc` + TOC 样式 +
    updateFields），但限制清单里还写着「无目录（TOC）生成」。
    """
    from docgen.render.docx import _render_toc  # noqa: F401  （存在即已实现）

    text = (ROOT / "LIMITATIONS.md").read_text(encoding="utf-8")
    for pattern in ("无目录（TOC）生成", "无目录生成", "不支持目录"):
        assert pattern not in text, f"限制清单把已实现的功能写成了限制: {pattern}"


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


# --------------------------------------------------------------------------
# 仓库结构（只在有 .git 的检出里跑；打好的源码包里没有 .git）
# --------------------------------------------------------------------------
def _git(*args: str) -> str:
    import subprocess

    result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=False)
    return result.stdout.strip()


def _git_available() -> bool:
    return (ROOT / ".git").exists() and bool(_git("rev-parse", "--git-dir"))


needs_git = pytest.mark.skipif(not _git_available(), reason="不是在 git 检出里运行")


@needs_git
def test_main_is_the_curated_release_line() -> None:
    """发布线 `main` 是 8 个线性提交（squash 后的里程碑）。"""
    assert _git("rev-list", "--count", "main") == "8"
    assert _git("rev-list", "--merges", "--count", "main") == "0"


@needs_git
def test_dev_shares_history_with_main() -> None:
    """`dev` 必须**从 `main` 展开**，否则 `git merge main` 会失败。

    实测踩到：两条线各自 orphan，merge 报 `refusing to merge unrelated histories`。

    判定：两条线必须有**共同祖先**（分叉点），且 `dev` 的根提交与 `main` 的根提交
    相同——这才说明「dev 从 main 签出」。
    不要断言 `main` 是 `dev` 的祖先：`dev` 可以已经领先（实测就因这个写法误报）。
    """
    assert _git("merge-base", "main", "dev"), "main 与 dev 没有共同祖先（历史无关）"
    assert _git("rev-list", "--max-parents=0", "dev") == _git(
        "rev-list", "--max-parents=0", "main"
    ), "两条线的根提交不同（dev 不是从 main 签出的）"


@needs_git
def test_v01_tag_points_at_the_pruning_baseline() -> None:
    """`v0.1` 必须指向**剪枝版基线**，而不是被相对位置搞错的别的提交。

    实测踩到：用 `main~1` 定位，结果指向了第 7 条（标题缩进）而不是第 2 条剪枝版。
    这里改用**内容特征**判断：剪枝版没有 Word 后端。
    """
    subject = _git("log", "-1", "--pretty=%s", "v0.1^{commit}")
    assert "剪枝版 v0.1" in subject, f"v0.1 指向了: {subject}"
    assert "docx.py" not in _git("ls-tree", "-r", "--name-only", "v0.1^{commit}")


@needs_git
def test_beta_tag_marks_a_commit_whose_version_is_beta() -> None:
    """`v0.1.0b1` 必须打在一个**版本号确实是预发布**的提交上。

    不要断言它等于某个分支的 tip：版本号可能在协作线上先 bump
    （实测踩到：β 标签本该在 `dev`，却按"main 的 tip"去断言而失败）。
    用内容判断更稳：该提交的 `pyproject.toml` 版本必须是 0.1.0b1。
    """
    version = _git("show", "v0.1.0b1^{commit}:pyproject.toml")
    match = re.search(r'^version = "([^"]+)"', version, re.MULTILINE)
    assert match is not None, "取不到 v0.1.0b1 指向提交的版本号"
    assert match.group(1) == "0.1.0b1", f"β 标签指向的提交版本是 {match.group(1)}"
    # 并且它必须落在**发布线或其协作线**上（不能是个孤儿提交）
    reachable = _git("branch", "-a", "--contains", "v0.1.0b1^{commit}")
    assert "main" in reachable or "dev" in reachable, f"β 标签不在任何分支的历史里: {reachable!r}"


@needs_git
def test_fine_grained_history_is_archived() -> None:
    """细粒度开发历史要有归档 ref（否则策展后就找不到了）。

    不写死条数——归档会随开发增长。
    """
    count = _git("rev-list", "--count", "history/fine-grained^{commit}")
    assert count.isdigit() and int(count) >= 36, f"归档历史条数异常: {count}"
    # 归档线必须含剪枝版基线之前的那种细粒度提交（抽查一条早期的）
    subjects = _git("log", "--format=%s", "history/fine-grained^{commit}")
    assert "初始化 docgen(e)骨架" in subjects


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

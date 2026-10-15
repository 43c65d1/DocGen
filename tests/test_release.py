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
    ["QUICKSTART.md", "LIMITATIONS.md", "FEEDBACK.md", "CHANGELOG.md", "README.md"],
)
def test_release_documents_exist(name: str) -> None:
    """发布测试版必须带的文档（面向使用者）不能缺。"""
    path = ROOT / name
    assert path.is_file(), f"缺少发布文档: {name}"
    assert path.stat().st_size > 500, f"{name} 内容过少，像是空壳"


def test_handoff_document_exists() -> None:
    """开发交接文档要随仓库提供（接手改动的人靠它）。"""
    path = ROOT / "HANDOFF.md"
    assert path.is_file(), "缺少 HANDOFF.md"
    assert path.stat().st_size > 800, "HANDOFF.md 内容过少"


def test_handoff_document_is_about_development() -> None:
    """`HANDOFF.md` 讲的是**开发**，不讲仓库维护。

    它随仓库上传，只放"运行/贡献所需"的信息；git 分支/发布流程这类自用内容
    不放在仓库里（维护者自己找地方存）。这里只断言文档的**主题**，
    不检测本地有没有别的文件、也不检测 git 状态——测试本身会上传，
    不该依赖某个人的本地布局。
    """
    handoff = (ROOT / "HANDOFF.md").read_text(encoding="utf-8")
    topics = set(re.findall(r"^## (.+)$", handoff, re.MULTILINE))
    for topic in ("分支模型", "发布流程（清单）", "怎么同步", "git 踩坑记录"):
        assert topic not in topics, f"HANDOFF.md 混入了 git 维护章节: {topic}"


def test_development_manual_is_shipped() -> None:
    """开发手册（原始规格）要随包发布——错误码等文档引用它。"""
    assert (ROOT / "docs" / "development-manual.md").is_file()


def test_package_script_exists_and_mentions_archive() -> None:
    script = ROOT / "scripts" / "package.sh"
    assert script.is_file()
    text = script.read_text(encoding="utf-8")
    assert "tar" in text and "zip" in text


@pytest.mark.parametrize(
    "name",
    [
        "QUICKSTART.md",
        "LIMITATIONS.md",
        "FEEDBACK.md",
        "CHANGELOG.md",
        "README.md",
        "HANDOFF.md",
    ],
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


# --------------------------------------------------------------------------
# 脚本的平台变体：bash / PowerShell / cmd 必须同步演化
#
# 三个入口做同一件事，所以关键约束要**逐个**检查——否则很容易改了 bash 忘了 pwsh，
# 使用者恰好用另一个入口就踩空（实测：cmd 里的中文注释会被 cmd.exe 按控制台代码页
# 读成乱码并当命令执行）。
# --------------------------------------------------------------------------
SCRIPTS = ROOT / "scripts"


@pytest.mark.parametrize("name", ["setup.sh", "setup.ps1"])
def test_setup_variants_share_the_same_contract(name: str) -> None:
    """`setup.sh` 与 `setup.ps1` 必须遵守同一组约束。"""
    text = (SCRIPTS / name).read_text(encoding="utf-8")
    # 三个候选来源都要有：镜像、PyPI、代理
    assert "tsinghua" in text, f"{name} 少了镜像候选"
    assert "pypi.org" in text, f"{name} 少了 PyPI 候选"
    assert "127.0.0.1:7897" in text, f"{name} 少了代理候选"
    # 手动指定来源的出口
    assert "--index" in text and "--proxy" in text, f"{name} 少了手动指定参数"
    # --dev 开关（PowerShell 版用 -Dev/--dev，bash 版只有 --dev）
    assert "dev" in text.lower(), f"{name} 少了 --dev"
    # 未知参数要拒绝，不能静默忽略
    assert "未知参数" in text, f"{name} 没有拒绝未知参数"


@pytest.mark.parametrize("name", ["setup.ps1", "package.ps1"])
def test_pwsh_variants_sync_frozen(name: str) -> None:
    """PowerShell 版同步也要带 `--frozen`（不改写 uv.lock）。

    bash 版早就有这条断言；pwsh 版必须一致，否则用 PowerShell 装一次
    就把锁文件里的 URL 换成镜像地址了。
    """
    if name == "package.ps1":
        pytest.skip("打包脚本不做依赖同步")
    text = (SCRIPTS / name).read_text(encoding="utf-8")
    assert "--frozen" in text, f"{name} 的同步没带 --frozen"


@pytest.mark.parametrize("name", ["package.sh", "package.ps1"])
def test_package_variants_share_the_same_contract(name: str) -> None:
    """`package.sh` 与 `package.ps1` 必须产出同样的东西。"""
    text = (SCRIPTS / name).read_text(encoding="utf-8")
    # 两种归档都要出
    assert "tar" in text and "zip" in text, f"{name} 少了归档格式"
    # 版本号取自 pyproject.toml（唯一真源）
    assert "pyproject.toml" in text, f"{name} 没从 pyproject 读版本"
    # 打包自检：不该混进构建产物
    assert "output.html" in text and "output.docx" in text, f"{name} 少了示例产物清理"
    assert "__pycache__" in text, f"{name} 少了缓存清理"
    # egg-info 是构建产物（.gitignore 里也有），必须排掉——
    # 实测 bash 版曾把它打进包（pwsh 版按清单复制所以没带），两边要一致
    assert "egg-info" in text, f"{name} 少了 egg-info 清理"


@pytest.mark.parametrize("name", ["setup.cmd", "package.cmd"])
def test_cmd_wrappers_exist_and_delegate(name: str) -> None:
    """cmd 入口要薄：只是转发给同目录的 .ps1。"""
    text = (SCRIPTS / name).read_text(encoding="utf-8")
    ps1 = name.replace(".cmd", ".ps1")
    assert ps1 in text, f"{name} 没有转发给 {ps1}"
    assert "%~dp0" in text, f"{name} 应该用 %~dp0 定位同目录脚本"


def test_cmd_files_are_ascii_only() -> None:
    """`.cmd` 必须纯 ASCII。

    实测踩到：cmd 文件里的中文注释会被 cmd.exe 按**控制台代码页**解读成乱码，
    还可能被当成命令执行（报 `'的' is not recognized as an internal command`）。
    所以 .cmd 里只写英文注释。
    """
    cmd_files = sorted(SCRIPTS.glob("*.cmd"))
    assert cmd_files, "找不到任何 .cmd 文件"
    for path in cmd_files:
        raw = path.read_bytes()
        non_ascii = [b for b in raw if b > 0x7F]
        assert not non_ascii, f"{path.name} 含非 ASCII 字节（cmd 会读成乱码）"


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
    """面向使用者的文档必须都能从 README 找到入口。"""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for name in ("QUICKSTART.md", "LIMITATIONS.md", "FEEDBACK.md"):
        assert name in readme, f"README 没有链接 {name}"


def test_readme_describes_current_output_format() -> None:
    """README 必须描述**当前**产出格式（只有 Word）。

    这条抓过两次过时：README 一度只讲 HTML（Word 后端还没写），
    后来又同时讲两个后端（HTML 已移除）。
    """
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert ".docx" in readme, "README 应说明产出是 .docx"
    assert "ECMA-376" in readme, "应说明产出过官方 schema 校验"
    # HTML 后端已移除：README 不该再把它当能力宣传
    assert "→ HTML / Word" not in readme
    assert "output.html" not in readme
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


def test_pyproject_has_no_local_junk_paths() -> None:
    """`pyproject.toml` 里不该出现**只在本机存在**的目录。

    这类垃圾（虚拟环境、工具缓存、临时探针目录）是本地状态的产物，
    别人机器上根本没有；它们该由 `.gitignore` 管，而不是写进工程配置。
    实测：这些排除本是死配置——ruff 默认遵守 gitignore，mypy 只跑 src/tests，
    去掉后 CI 依然全绿。
    """
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    for junk in (".venv", "venv-dev", ".uv-cache", "pytest-tmp", ".tmp", "cache/"):
        assert junk not in text, f"pyproject.toml 里出现了本机路径 {junk!r}"
    config = _pyproject()
    assert "exclude" not in config["tool"]["mypy"], "mypy 只跑 src tests，不需要 exclude"


def test_pyproject_has_no_internal_doc_references() -> None:
    """`pyproject.toml` 不该引用仓库内部的文档编号/内部代号。

    读者可能只拿到这一个文件（或只看 PyPI 元数据页），"手册 §12" 这类索引
    对他们没有意义。要让说明自足。
    """
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    for marker in ("手册", "§", "Hard Version", "剪枝版"):
        assert marker not in text, f"pyproject.toml 引用了内部概念 {marker!r}"

"""避头尾（行首行尾禁则）与中文标点压缩。

实测（Word 2016+，225 字标点密集段落，宋体 11pt / 1.5 倍行距）：

| 设置 | 行首标点 |
|---|---|
| 母版原样：``eastAsia="en-US"`` + ``doNotCompress`` | **2 处**（``）」``、``）``） |
| 只加 ``w:kinsoku`` / ``w:overflowPunct`` | 2 处 |
| 再加 ``compressPunctuation`` | 1 处 |
| 再把 ``eastAsia`` 改成 ``zh-CN`` | **0 处** |

所以「写了 kinsoku 就万事大吉」是错的——**文档默认语言**才决定 Word 用哪套禁则表。
"""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

import pytest

from docgen.config import Config, load_config
from docgen.errors import DocGenError
from docgen.parser.dfm import parse_dfm
from docgen.render.docx import render_docx_bytes

BASE = 'config_version = "0.1"\n\n[math]\nengine = "plain"\n'


def _config(tmp_path: Path, extra: str = "") -> Config:
    path = tmp_path / "config.toml"
    path.write_text(BASE + extra, encoding="utf-8")
    return load_config(path)


def _parts(tmp_path: Path, extra: str = "") -> tuple[str, str]:
    data = render_docx_bytes(parse_dfm("正文。\n"), _config(tmp_path, extra))
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return (
            archive.read("word/settings.xml").decode("utf-8"),
            archive.read("word/styles.xml").decode("utf-8"),
        )


def _attr(settings: str, element: str) -> str:
    match = re.search(rf"<w:{element} w:val=\"([^\"]+)\"", settings)
    assert match is not None, f"settings.xml 里没有 w:{element}"
    return match.group(1)


# --------------------------------------------------------------------------
# 默认：全开
# --------------------------------------------------------------------------
def test_default_east_asian_typography_is_enabled(tmp_path: Path) -> None:
    settings, styles = _parts(tmp_path)
    assert _attr(settings, "kinsoku") == "true"
    assert _attr(settings, "overflowPunct") == "true"
    assert _attr(settings, "autoSpaceDE") == "true"
    assert _attr(settings, "autoSpaceDN") == "true"
    assert _attr(settings, "characterSpacingControl") == "compressPunctuation"
    # 语言标记是决定性因素：en-US 时 Word 仍会把「）」放到行首
    assert 'w:eastAsia="zh-CN"' in styles


def test_settings_children_follow_schema_order(tmp_path: Path) -> None:
    """``CT_Settings`` 是 sequence：插错顺序 Word 会静默忽略该设置。

    不用整份 XSD 校验 ``settings.xml``：模板自带 ``w:zoom`` 缺 ``w:percent``、
    ``w14:docId`` 等历史问题，会淹掉真正的问题；这里只校验我们关心的顺序。
    """
    from docgen.render.ooxml import CHILD_ORDER

    settings, _ = _parts(tmp_path)
    order = CHILD_ORDER["w:settings"]
    names = [f"w:{name}" for name in re.findall(r"<w:(\w+)[ />]", settings)]
    ranks = [order.index(name) for name in names if name in order]
    assert ranks == sorted(ranks), "settings 子元素顺序不符合 CT_Settings 的 sequence"


# --------------------------------------------------------------------------
# 可配
# --------------------------------------------------------------------------
def test_east_asia_language_can_be_changed(tmp_path: Path) -> None:
    _, styles = _parts(tmp_path, '\n[document]\neast_asia_lang = "ja-JP"\n')
    assert 'w:eastAsia="ja-JP"' in styles


def test_kinsoku_can_be_disabled(tmp_path: Path) -> None:
    settings, _ = _parts(tmp_path, "\n[document]\nkinsoku = false\n")
    assert _attr(settings, "kinsoku") == "false"


def test_overflow_punct_can_be_disabled(tmp_path: Path) -> None:
    settings, _ = _parts(tmp_path, "\n[document]\noverflow_punct = false\n")
    assert _attr(settings, "overflowPunct") == "false"


def test_auto_space_can_be_disabled(tmp_path: Path) -> None:
    settings, _ = _parts(tmp_path, "\n[document]\nauto_space = false\n")
    assert _attr(settings, "autoSpaceDE") == "false"
    assert _attr(settings, "autoSpaceDN") == "false"


def test_punctuation_compression_can_be_disabled(tmp_path: Path) -> None:
    settings, _ = _parts(tmp_path, "\n[document]\ncompress_punctuation = false\n")
    assert _attr(settings, "characterSpacingControl") == "doNotCompress"


# --------------------------------------------------------------------------
# 非法值要报错（不静默取默认）
# --------------------------------------------------------------------------
def test_invalid_language_tag_raises(tmp_path: Path) -> None:
    with pytest.raises(DocGenError) as caught:
        render_docx_bytes(
            parse_dfm("正文。\n"), _config(tmp_path, '\n[document]\neast_asia_lang = "chinese"\n')
        )
    assert caught.value.code == "E5001"


def test_invalid_boolean_raises(tmp_path: Path) -> None:
    with pytest.raises(DocGenError) as caught:
        render_docx_bytes(
            parse_dfm("正文。\n"), _config(tmp_path, '\n[document]\nkinsoku = "maybe"\n')
        )
    assert caught.value.code == "E5001"

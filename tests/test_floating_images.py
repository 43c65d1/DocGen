"""浮动图片 / 文字环绕：``[[img:... wrap=...]]``。"""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

import pytest

from docgen.config import Config, load_config
from docgen.errors import E_CONFIG, DocGenError
from docgen.ir import ImageBlock
from docgen.parser.dfm import parse_dfm
from docgen.render.docx import render_docx_bytes
from docgen.render.ooxml_check import validate_with_schema

FIXTURES = Path(__file__).parent / "fixtures"
BASE = 'config_version = "0.1"\n'


def _config(tmp_path: Path, extra: str = "") -> Config:
    path = tmp_path / "c.toml"
    path.write_text(BASE + extra, encoding="utf-8")
    return load_config(path)


def _document(tmp_path: Path, markdown: str, extra: str = "") -> str:
    data = render_docx_bytes(parse_dfm(markdown), _config(tmp_path, extra), base_dir=FIXTURES)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return archive.read("word/document.xml").decode("utf-8")


def _extent_cx(document: str) -> int:
    return int(re.findall(r'<wp:extent cx="(\d+)"', document)[0])


def test_parse_float_attributes() -> None:
    blocks = parse_dfm("[[img:pics/photo.png width=2cm wrap=square align=right vpos=0.5cm]]\n")
    block = blocks[0]
    assert isinstance(block, ImageBlock)
    assert block.wrap == "square"
    assert block.align == "right"
    assert block.vpos == "0.5cm"
    assert block.width == "2cm"


def test_default_is_still_inline(tmp_path: Path) -> None:
    document = _document(tmp_path, "[[img:pics/photo.png width=2cm]]\n")
    assert "<wp:inline" in document
    assert "<wp:anchor" not in document


def test_square_wrap_anchor(tmp_path: Path) -> None:
    document = _document(tmp_path, "[[img:pics/photo.png width=2cm wrap=square align=right]]\n")
    assert '<wp:anchor distT="114300"' in document
    assert 'behindDoc="0"' in document
    assert (
        '<wp:positionH relativeFrom="margin"><wp:align>right</wp:align></wp:positionH>' in document
    )
    assert '<wp:wrapSquare wrapText="bothSides"/>' in document
    assert abs(_extent_cx(document) - 720000) <= 2000


def test_anchor_child_order_is_schema_order(tmp_path: Path) -> None:
    document = _document(tmp_path, "[[img:pics/photo.png width=2cm wrap=square]]\n")
    anchor_start = document.index("<wp:anchor")
    order = [
        document.index("<wp:simplePos", anchor_start),
        document.index("<wp:positionH", anchor_start),
        document.index("<wp:positionV", anchor_start),
        document.index("<wp:extent", anchor_start),
        document.index("<wp:wrapSquare", anchor_start),
        document.index("<wp:docPr", anchor_start),
    ]
    assert order == sorted(order)


def test_top_and_bottom_and_behind(tmp_path: Path) -> None:
    top_bottom = _document(tmp_path, "[[img:pics/photo.png wrap=top-bottom]]\n")
    assert "<wp:wrapTopAndBottom/>" in top_bottom
    behind = _document(tmp_path, "[[img:pics/photo.png wrap=behind]]\n")
    assert 'behindDoc="1"' in behind
    assert "<wp:wrapNone/>" in behind


def test_dist_and_vpos_override(tmp_path: Path) -> None:
    document = _document(tmp_path, "[[img:pics/photo.png wrap=square dist=0.2cm vpos=0.5cm]]\n")
    assert 'distT="72000"' in document
    assert "<wp:posOffset>180000</wp:posOffset>" in document


def test_config_defaults_and_marker_override(tmp_path: Path) -> None:
    extra = '\n[image]\nwrap = "square"\nalign = "left"\ndist = "0.1cm"\n'
    document = _document(tmp_path, "[[img:pics/photo.png width=2cm]]\n", extra)
    assert '<wp:wrapSquare wrapText="bothSides"/>' in document
    assert "<wp:align>left</wp:align>" in document
    assert 'distT="36000"' in document
    override = _document(tmp_path, "[[img:pics/photo.png wrap=behind]]\n", extra)
    assert 'behindDoc="1"' in override


def test_relative_height_is_unique(tmp_path: Path) -> None:
    document = _document(
        tmp_path,
        "[[img:pics/photo.png wrap=square]]\n\n[[img:pics/photo.png wrap=square]]\n",
    )
    heights = re.findall(r'relativeHeight="(\d+)"', document)
    assert len(set(heights)) == len(heights) == 2


def test_floating_document_passes_wml_schema(tmp_path: Path) -> None:
    document = _document(
        tmp_path,
        "[[img:pics/photo.png width=2cm wrap=square align=right dist=0.2cm vpos=0.3cm]]\n",
    )
    assert validate_with_schema(document) == []


def test_invalid_wrap_reports_config_error(tmp_path: Path) -> None:
    with pytest.raises(DocGenError) as error:
        _document(tmp_path, "[[img:pics/photo.png wrap=circular]]\n")
    assert error.value.code == E_CONFIG


def test_invalid_dist_reports_config_error(tmp_path: Path) -> None:
    with pytest.raises(DocGenError) as error:
        _document(tmp_path, "[[img:pics/photo.png wrap=square dist=abc]]\n")
    assert error.value.code == E_CONFIG


def test_negative_dist_reports_config_error(tmp_path: Path) -> None:
    with pytest.raises(DocGenError) as error:
        _document(tmp_path, "[[img:pics/photo.png wrap=square dist=-1cm]]\n")
    assert error.value.code == E_CONFIG

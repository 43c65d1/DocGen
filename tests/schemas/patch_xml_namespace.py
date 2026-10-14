"""给 vendored 的 wml.xsd 补 `xml:` 命名空间 import（幂等）。

官方 wml.xsd 引用了 `xml:space`（经 ``shared-commonSimpleTypes.xsd`` 的 ``ST_String``），
但自己没 `xs:import` XML 命名空间，lxml 会报
``attribute 'ref': The QName value '{...}space' does not resolve``。
这里注入一行 import 指向随附的最小 `xml.xsd`，让离线校验可用。
"""

from __future__ import annotations

import sys
from pathlib import Path

MARKER = 'id="xml"'
IMPORT = '<xsd:import id="xml" namespace="http://www.w3.org/XML/1998/namespace" schemaLocation="xml.xsd"/>'


def patch(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    if MARKER in text:
        return False
    needle = "<xsd:schema"
    index = text.index(">", text.index(needle)) + 1
    patched = text[:index] + "\n  " + IMPORT + text[index:]
    path.write_text(patched, encoding="utf-8")
    return True


if __name__ == "__main__":
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "tests/schemas/ecma-376/wml.xsd")
    print("patched" if patch(target) else "already patched")

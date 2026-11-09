"""输入文件的文本解码（UTF-8 优先，GB18030 兜底）。

DocGen 的内部文本约定是 **UTF-8**（IR、解析、渲染都按 UTF-8 处理）。
但真实中文环境里，DFM/config/文献库可能是 Windows 记事本存的 GBK/GB2312；
直接 ``decode("utf-8")`` 会抛 ``UnicodeDecodeError``（文献库那处甚至没被捕获，
会冒成 traceback）。

策略（best effort，不承诺覆盖所有编码）：

1. 有 UTF-8 BOM → ``utf-8-sig``；
2. 否则先试 ``utf-8``；
3. 再试 ``gb18030``（GBK/GB2312 的超集，覆盖绝大多数中文旧文件）；
4. 都不行 → ``E5001``，提示已尝试的编码。

输出始终是 UTF-8（docx/XML），编码问题只影响"读入"。
"""

from __future__ import annotations

import codecs

from .errors import E_CONFIG, DocGenError

__all__ = ["decode_text"]

#: 解码尝试顺序（utf-8 由 BOM 分支单独处理）
FALLBACK_ENCODINGS = ("gb18030",)


def decode_text(raw: bytes, *, path: str | None = None) -> str:
    """把字节解码成文本：UTF-8（含 BOM）→ GB18030；失败报 ``E5001``。"""
    label = path or "<bytes>"
    if raw.startswith(codecs.BOM_UTF8):
        try:
            return raw.decode("utf-8-sig")
        except UnicodeDecodeError as exc:  # pragma: no cover - BOM 正确时不会发生
            raise DocGenError(E_CONFIG, f"文件不是合法 UTF-8（BOM）: {label}: {exc}") from None

    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        pass

    for encoding in FALLBACK_ENCODINGS:
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue

    tried = " / ".join(("utf-8", *FALLBACK_ENCODINGS))
    raise DocGenError(
        E_CONFIG,
        f"无法识别文件编码: {label}（已尝试 {tried}；请另存为 UTF-8）",
    )

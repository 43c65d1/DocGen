"""输入规范化：去 BOM + 统一换行为 LF。

入口只有一个 :func:`normalize_text`：CLI 读文件后、解析前必须调用它，
这样下游（IR、行号、渲染）永远只面对 LF 文本。
"""


def normalize_text(text: str) -> str:
    text = text.removeprefix("\ufeff")
    return text.replace("\r\n", "\n").replace("\r", "\n")

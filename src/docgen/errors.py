"""统一错误码与错误对象（手册 §11）。

错误码是契约的一部分：CLI 退出码、``check --json`` 输出都依赖它们。
"""

# --- 错误码常量 ---------------------------------------------------------
E_CIRCULAR_INHERITANCE = "E1001"  # 循环继承
E_INHERITANCE_DEPTH = "E1002"  # 继承深度超限
E_UNKNOWN_STYLE = "E1003"  # 引用不存在的样式
E_UNKNOWN_LANGUAGE = "E2001"  # 未知语言
E_UNCLOSED_MARKER = "E3001"  # 标记未闭合
E_SYNTAX = "E4001"  # 语法错误
E_CONFIG = "E5001"  # config 文件缺失/版本不符


class DocGenError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        file: str = "",
        line: int = 0,
        col: int = 0,
    ) -> None:
        self.code = code
        self.message = message
        self.file = file
        self.line = line
        self.col = col
        super().__init__(str(self))

    def __str__(self) -> str:
        if self.file:
            return f"{self.file}:{self.line}:{self.col}:{self.code}:{self.message}"
        return f"{self.code}:{self.message}"

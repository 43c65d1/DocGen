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

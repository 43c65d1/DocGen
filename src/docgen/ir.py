from dataclasses import dataclass


@dataclass(frozen=True)
class Text:
    content: str


@dataclass(frozen=True)
class Heading:
    level: int
    content: list
    source_line: int


@dataclass(frozen=True)
class Paragraph:
    content: list
    source_line: int

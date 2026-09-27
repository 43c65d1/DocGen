from docgen.ir import Heading, Paragraph, Text
from docgen.parser.dfm import parse_dfm


def test_minimal_ir() -> None:
    text = "# Hello\n\nWorld\n"
    blocks = parse_dfm(text)

    assert blocks == [
        Heading(level=1, content=[Text("Hello")], source_line=1),
        Paragraph(content=[Text("World")], source_line=3),
    ]

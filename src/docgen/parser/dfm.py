from ..ir import Heading, Paragraph, Text


def parse_dfm(text: str) -> list:
    blocks: list = []
    for i, line in enumerate(text.splitlines(), start=1):
        line = line.rstrip()
        if not line:
            continue

        if line.startswith("## "):
            blocks.append(
                Heading(level=2, content=[Text(line[3:])], source_line=i)
            )
        elif line.startswith("# "):
            blocks.append(
                Heading(level=1, content=[Text(line[2:])], source_line=i)
            )
        else:
            blocks.append(
                Paragraph(content=[Text(line)], source_line=i)
            )
    return blocks

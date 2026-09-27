import argparse
import sys
from pathlib import Path

from .errors import DocGenError
from .normalize import normalize_text
from .parser.dfm import parse_dfm


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="docgen")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_dump = sub.add_parser("dump-ir", help="解析 DFM 并输出 IR")
    p_dump.add_argument("input", type=Path)

    p_build = sub.add_parser("build", help="生成 HTML")
    p_build.add_argument("input", type=Path)
    p_build.add_argument("-o", "--output", type=Path, default=Path("output.html"))

    args = parser.parse_args(argv)

    try:
        if args.cmd == "dump-ir":
            text = normalize_text(args.input.read_text(encoding="utf-8"))
            blocks = parse_dfm(text)
            for block in blocks:
                print(block)
            return 0

        if args.cmd == "build":
            print("build 还没实现，先跑 dump-ir")
            return 0

    except DocGenError as e:
        print(e, file=sys.stderr)
        return 1
    except FileNotFoundError as e:
        print(f"E5001: 文件不存在: {e}", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())

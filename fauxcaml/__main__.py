import argparse

from fauxcaml import build


def create_parser():
    ap = argparse.ArgumentParser(
        prog="fauxcamlc",
        description="Compiles an OCaml source file to an x86-64 executable.",
        epilog="project homepage: https://github.com/eignnx/fauxcaml",
    )

    ap.add_argument(
        "source_file",
        metavar="SRC",
        type=str,
        help="the file to compile",
    )

    ap.add_argument(
        "-o",
        dest="exe_file",
        metavar="EXE",
        type=str,
        default=None,
        help="the name of the executable to create",
    )

    return ap


if __name__ == "__main__":
    ap = create_parser()
    args = ap.parse_args()
    build.compile_from_source_file(args.source_file, args.exe_file)

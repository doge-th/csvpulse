"""Command line interface."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from . import __version__
from .profile import profile_file
from .report import render_json, render_markdown, render_table


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="csvpulse",
        description="Take the pulse of a CSV file: column types, fill rate, "
                    "uniques, numeric ranges, top values, ragged and "
                    "duplicate rows — one command, zero dependencies.",
        epilog="examples:  csvpulse data.csv  ·  csvpulse data.csv --delimiter ';'  ·  "
               "csvpulse data.csv --json",
    )
    p.add_argument("path", metavar="FILE", help="the CSV file to profile")
    p.add_argument("--delimiter", metavar="CHAR",
                   help="field separator (default: sniffed, fallback ',')")
    p.add_argument("--encoding", metavar="ENC",
                   help="text encoding (default: BOM/utf-8 sniff, latin-1 fallback)")
    p.add_argument("--no-header", action="store_true",
                   help="the first row is data, not a header")
    p.add_argument("--top", type=int, default=3, metavar="N",
                   help="top values to show per column (default 3)")
    p.add_argument("--json", dest="fmt", action="store_const", const="json",
                   help="machine-readable JSON output")
    p.add_argument("--markdown", "--md", dest="fmt", action="store_const",
                   const="markdown", help="markdown output for issues/PRs")
    p.add_argument("--version", action="version",
                   version=f"csvpulse {__version__}")
    return p


def main(argv=None) -> int:
    parser = build_parser()
    opts = parser.parse_args(argv)
    if opts.top < 0:
        parser.error("--top must be >= 0")
    if opts.delimiter and len(opts.delimiter) != 1:
        parser.error("--delimiter must be a single character")

    path = Path(opts.path)
    if not path.is_file():
        print(f"csvpulse: no such file: {opts.path}", file=sys.stderr)
        return 1
    try:
        prof = profile_file(path, opts.delimiter, opts.encoding,
                            not opts.no_header, opts.top)
    except UnicodeDecodeError as e:
        print(f"csvpulse: cannot decode {opts.path} as {opts.encoding}: {e}",
              file=sys.stderr)
        return 1
    except csv.Error as e:
        print(f"csvpulse: CSV parsing failed: {e}", file=sys.stderr)
        return 1
    except OSError as e:
        print(f"csvpulse: {e}", file=sys.stderr)
        return 1

    renderer = {"table": render_table, "json": render_json,
                "markdown": render_markdown}[opts.fmt or "table"]
    print(renderer(prof, opts))
    return 0


if __name__ == "__main__":
    sys.exit(main())

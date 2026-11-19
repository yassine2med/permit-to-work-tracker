"""Command line entry: python -m ptw report <csv> --now <ISO time>."""
from __future__ import annotations

import argparse
import sys
from datetime import datetime

from .core import check, format_report, load_permits


def main(argv: list[str] | None = None) -> int:
    """Run the CLI. Exit code 0 clean, 1 findings, 2 bad input."""
    parser = argparse.ArgumentParser(prog="ptw", description="Check a permit-to-work log.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    rep = sub.add_parser("report", help="print findings")
    rep.add_argument("csv")
    rep.add_argument("--now", default=None, help="ISO time, default is the current time")
    args = parser.parse_args(argv)
    try:
        now = datetime.fromisoformat(args.now) if args.now else datetime.now()
        permits = load_permits(args.csv)
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    findings = check(permits, now)
    print(format_report(permits, findings))
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())

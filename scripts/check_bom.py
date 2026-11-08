"""Fail if any tracked file starts with a UTF-8 BOM.

Run from anywhere:

    python scripts/check_bom.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOM = b"\xef\xbb\xbf"


def tracked_files() -> list[Path]:
    try:
        output = subprocess.check_output(
            ["git", "ls-files", "-z"],
            cwd=ROOT,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError):
        print("Could not list tracked files (git is unavailable).")
        return []
    return [
        ROOT / name
        for name in output.decode("utf-8", "surrogateescape").split("\0")
        if name
    ]


def main() -> int:
    files = tracked_files()
    if not files:
        return 0

    bad: list[Path] = []
    for path in files:
        try:
            with path.open("rb") as handle:
                if handle.read(3) == BOM:
                    bad.append(path)
        except OSError:
            continue

    if bad:
        print("UTF-8 BOM found in tracked files:")
        for path in bad:
            print(f"  - {path.relative_to(ROOT)}")
        return 1

    print(f"OK: no UTF-8 BOM in {len(files)} tracked files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

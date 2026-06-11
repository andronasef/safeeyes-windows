#!/usr/bin/env python3
# Safe Eyes is a utility to remind you to take break frequently
# to protect your eyes from eye strain.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""Compile every .po translation into a .mo file (cross-platform, Babel-based).

Run this once after cloning, before launching from source, so translations are
available:

    python build_messages.py

The packaged build (``pip install .`` / sdist / wheel) compiles these
automatically via setup.py, so this script is only needed for source runs.
"""

import io
import sys
from pathlib import Path

# Empty date headers (left by some translation platforms) make Babel's strict
# parser raise; give them a placeholder so compilation matches gettext msgfmt.
_EMPTY_DATE_HEADERS = (
    (b'"POT-Creation-Date: \\n"', b'"POT-Creation-Date: 2000-01-01 00:00+0000\\n"'),
    (b'"PO-Revision-Date: \\n"', b'"PO-Revision-Date: 2000-01-01 00:00+0000\\n"'),
)

LOCALE_DIR = Path(__file__).resolve().parent / "safeeyes" / "config" / "locale"


def compile_po(po_path: Path, mo_path: Path) -> None:
    from babel.messages.mofile import write_mo
    from babel.messages.pofile import read_po

    data = po_path.read_bytes()
    for empty, placeholder in _EMPTY_DATE_HEADERS:
        data = data.replace(empty, placeholder)
    catalog = read_po(io.BytesIO(data))
    with open(mo_path, "wb") as mo:
        write_mo(mo, catalog)


def main() -> int:
    if not LOCALE_DIR.is_dir():
        print(f"Locale directory not found: {LOCALE_DIR}", file=sys.stderr)
        return 1

    ok = failed = 0
    for po_file in LOCALE_DIR.glob("*/LC_MESSAGES/*.po"):
        try:
            compile_po(po_file, po_file.with_suffix(".mo"))
            ok += 1
        except Exception as error:  # noqa: BLE001 - report and continue
            failed += 1
            lang = po_file.parent.parent.name
            print(f"  failed: {lang} -> {error!r}", file=sys.stderr)

    print(f"Compiled {ok} translation file(s){f', {failed} failed' if failed else ''}.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

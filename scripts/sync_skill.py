#!/usr/bin/env python3
"""Copy the tested projection code into the skill bundle.

The skill materialises into the sandbox on its own, so it cannot import from
the package. Rather than let a second copy of the maths drift out of step with
the tested one, this copies it and a test asserts the two are byte-identical.

    python scripts/sync_skill.py
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "stores_triage" / "projection.py"
TARGET = ROOT / "skills" / "stores-triage" / "scripts" / "projection.py"


def main() -> int:
    if not SOURCE.exists():
        print(f"missing {SOURCE}", file=sys.stderr)
        return 1
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    changed = not TARGET.exists() or TARGET.read_bytes() != SOURCE.read_bytes()
    shutil.copyfile(SOURCE, TARGET)
    print(f"{'updated' if changed else 'already in sync'}: {TARGET.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

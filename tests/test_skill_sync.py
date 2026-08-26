"""The skill's copy of the maths must not drift from the tested one."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "stores_triage" / "projection.py"
BUNDLED = ROOT / "skills" / "stores-triage" / "scripts" / "projection.py"


def test_skill_bundle_matches_the_tested_module():
    # If this fails, run: python scripts/sync_skill.py
    assert BUNDLED.exists(), "skill bundle is missing projection.py"
    assert BUNDLED.read_bytes() == SOURCE.read_bytes(), (
        "skills/stores-triage/scripts/projection.py has drifted from "
        "stores_triage/projection.py - run python scripts/sync_skill.py"
    )

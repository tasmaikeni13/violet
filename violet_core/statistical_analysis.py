"""Driver for the Violet analysis suite.

Runs every experiment the paper reports and writes the figures into
``figures/`` and the raw numbers into ``analysis/results/``.

    python violet_core/statistical_analysis.py [--quick]
"""

from __future__ import annotations

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ANALYSIS = os.path.join(ROOT, "analysis")

STEPS = [
    ("a1_invariants.py", "structural invariants of the reachable permutation set"),
    ("a2_statistics.py", "ciphertext statistics and plugboard transparency"),
    ("a3_diffusion.py", "diffusion and depth under both stepping regimes"),
    ("a4_security.py", "key material against work factor"),
]
SLOW = [("a5_attack.py", "exhaustive key recovery, seven scaled builds")]


def main() -> int:
    quick = "--quick" in sys.argv
    steps = STEPS if quick else STEPS + SLOW
    for script, description in steps:
        print(f"\n=== {script}: {description}")
        result = subprocess.run([sys.executable, os.path.join(ANALYSIS, script)])
        if result.returncode != 0:
            print(f"    {script} failed", file=sys.stderr)
            return result.returncode
    if quick:
        print("\n(skipping a5_attack.py; run without --quick for the full search)")
    print(f"\nfigures written to {os.path.join(ROOT, 'figures')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

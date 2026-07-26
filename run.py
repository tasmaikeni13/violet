#!/usr/bin/env python3
"""Violet launcher.

    python run.py test       validation suite for the cipher
    python run.py analyse    regenerate every figure in the Violet paper
    python run.py studio     interactive Tkinter interface
    python run.py hmv        build and self-test the HMV hash family
    python run.py papers     rebuild both PDFs
"""

from __future__ import annotations

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))


def sh(cmd, cwd=None):
    print(f"$ {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=cwd or ROOT).returncode


def main() -> int:
    what = sys.argv[1] if len(sys.argv) > 1 else "test"
    if what == "test":
        return sh([sys.executable, "violet_core/test_theorems.py"])
    if what == "analyse":
        return sh([sys.executable, "violet_core/statistical_analysis.py"] + sys.argv[2:])
    if what == "studio":
        return sh([sys.executable, "violet_studio/app.py"])
    if what == "hmv":
        rc = sh(["make"], cwd=os.path.join(ROOT, "HMV", "src"))
        if rc:
            return rc
        return sh([os.path.join(ROOT, "HMV", "src", "hmv_test")])
    if what == "papers":
        for folder, name in (("paper", "violet"), (os.path.join("HMV", "paper"), "hmv")):
            for _ in range(2):
                rc = sh(["pdflatex", "-interaction=nonstopmode", f"{name}.tex"],
                        cwd=os.path.join(ROOT, folder))
            if rc:
                return rc
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

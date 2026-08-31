"""Orchestrator - run the pipeline steps in order.

    python run_all.py                 # all steps 00..08
    python run_all.py --from 3 --to 6  # a range
    python run_all.py --limit 5        # pass --limit through to every step
    python run_all.py --only 1         # a single step

Step 03 is a manual checkpoint: if config/structure.yaml does not exist yet the
orchestrator runs `03_structure.py --detect` and stops so you can edit it.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PIPE = ROOT / "src" / "pipeline"
STEPS = [
    "00_extract_pages.py", "01_ocr.py", "02_clean_text.py", "03_structure.py",
    "04_tts.py", "05_smil.py", "06_package.py", "07_validate.py",
    "08_package_submit.py",
]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from", dest="start", type=int, default=0)
    ap.add_argument("--to", dest="end", type=int, default=len(STEPS) - 1)
    ap.add_argument("--only", type=int, default=None)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--chapter", default="")
    args = ap.parse_args()

    lo, hi = (args.only, args.only) if args.only is not None else (args.start, args.end)
    for i in range(lo, hi + 1):
        script = PIPE / STEPS[i]
        cmd = [sys.executable, str(script)]
        if args.limit:
            cmd += ["--limit", str(args.limit)]
        if args.chapter:
            cmd += ["--chapter", args.chapter]

        if i == 3 and not (ROOT / "config" / "structure.yaml").exists():
            print(">>> step 03: no config/structure.yaml yet - running --detect and stopping")
            subprocess.run([sys.executable, str(script), "--detect"], check=True)
            print(">>> edit config/structure.yaml, then rerun:  python run_all.py --from 3")
            return

        print(f"\n===== step {i:02d}: {STEPS[i]} =====")
        r = subprocess.run(cmd)
        if r.returncode != 0:
            sys.exit(f"step {i:02d} failed (exit {r.returncode})")

    print("\nall requested steps done.")


if __name__ == "__main__":
    main()

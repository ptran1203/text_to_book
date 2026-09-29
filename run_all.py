"""Orchestrator - run the pipeline steps in order.

    python run_all.py                 # all steps 00..08 - starts a NEW run
    python run_all.py --from 3 --to 6  # a range - continues the latest run
    python run_all.py --limit 5        # pass --limit through to every step
    python run_all.py --only 1         # a single step
    python run_all.py --from 3 --run-id 20260912_181123   # resume a specific past run
    python run_all.py --page-start 15 --page-end 40   # step 00 jumps straight into a page range

Each full run gets its own output/<run_id>/ folder (run_id = start time,
YYYYMMDD_HHMMSS). Step 00 (the entry point) always mints a fresh run_id unless
--run-id overrides it; every later step defaults to continuing whichever run
was started most recently, so a plain `--from 3` naturally resumes the run
step 00 already produced - no bookkeeping needed unless you want to target an
older run explicitly.

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
    ap.add_argument("--run-id", default="",
                     help="target a specific run instead of starting/continuing the latest one")
    ap.add_argument("--page-start", type=int, default=0,
                     help="step 00 only: first PDF page to extract (jump past front matter)")
    ap.add_argument("--page-end", type=int, default=0,
                     help="step 00 only: last PDF page to extract, inclusive")
    args = ap.parse_args()

    lo, hi = (args.only, args.only) if args.only is not None else (args.start, args.end)
    for i in range(lo, hi + 1):
        script = PIPE / STEPS[i]
        cmd = [sys.executable, str(script)]
        if args.limit:
            cmd += ["--limit", str(args.limit)]
        if args.chapter:
            cmd += ["--chapter", args.chapter]
        if args.run_id:
            cmd += ["--run-id", args.run_id]
        if i == 0:
            if args.page_start:
                cmd += ["--start", str(args.page_start)]
            if args.page_end:
                cmd += ["--end", str(args.page_end)]

        if i == 3 and not (ROOT / "config" / "structure.yaml").exists():
            print(">>> step 03: no config/structure.yaml yet - running --detect and stopping")
            detect_cmd = [sys.executable, str(script), "--detect"]
            if args.run_id:
                detect_cmd += ["--run-id", args.run_id]
            subprocess.run(detect_cmd, check=True)
            print(">>> edit config/structure.yaml, then rerun:  python run_all.py --from 3")
            return

        print(f"\n===== step {i:02d}: {STEPS[i]} =====")
        r = subprocess.run(cmd)
        if r.returncode != 0:
            sys.exit(f"step {i:02d} failed (exit {r.returncode})")

    print("\nall requested steps done.")


if __name__ == "__main__":
    main()

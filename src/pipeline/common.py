"""Shared helpers for the text_to_book DAISY pipeline.

Every step script does:

    import common
    cfg = common.load_config()
    common.use_latest_run(args.run_id)   # or common.start_run(...) - see below
    ...
    out = common.step_dir(3)          # -> <root>/output/<run_id>/step_03  (created)

Each *run* of the pipeline (one pass over the book, from PDF to submission
zip) gets its own timestamped folder, output/<run_id>/, so rerunning doesn't
clobber a previous run's output. 00_extract_pages.py is the entry point and
mints a fresh run_id by default (YYYYMMDD_HHMMSS); every later step defaults
to continuing the most recently started run (tracked in output/.current_run),
so the normal "run 00, then 01, then 02, ..." workflow needs no extra flags.
Pass --run-id explicitly to target a specific past run instead.

Step scripts are run directly (``python src/pipeline/03_structure.py``); they are
not importable as modules because their names start with a digit.  They import
this file by adding their own directory to ``sys.path`` first.
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import re
import subprocess
import sys
import time
import unicodedata
from datetime import datetime
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - surfaced immediately on first run
    print("PyYAML is required:  pip install pyyaml", file=sys.stderr)
    raise

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
CONFIG_DIR = ROOT / "config"
OUTPUT_DIR = ROOT / "output"

RUN_ID: str | None = None  # set once per process via start_run()/use_latest_run()


# ---------------------------------------------------------------------- runs
def _run_pointer() -> Path:
    return OUTPUT_DIR / ".current_run"


def new_run_id() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def start_run(explicit: str = "") -> str:
    """Begin a run (step 00 calls this): mint a fresh run_id, unless one is
    given explicitly, and remember it as 'latest' for the other steps."""
    global RUN_ID
    RUN_ID = explicit or new_run_id()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _run_pointer().write_text(RUN_ID, encoding="utf-8")
    dump_json(dict(run_id=RUN_ID, started_at=datetime.now().isoformat(timespec="seconds")),
              step_dir(0) / "run_info.json")
    return RUN_ID


def use_latest_run(explicit: str = "") -> str:
    """Resolve which run this step writes into: --run-id if given, else the
    most recently started run. Every step but 00 calls this."""
    global RUN_ID
    if explicit:
        RUN_ID = explicit
    elif _run_pointer().exists():
        RUN_ID = _run_pointer().read_text(encoding="utf-8").strip()
    else:
        sys.exit("no run in progress - run 00_extract_pages.py first, or pass --run-id YYYYMMDD_HHMMSS")
    return RUN_ID


# --------------------------------------------------------------------------- io
def step_dir(n: int, *, create: bool = True) -> Path:
    if not RUN_ID:
        raise RuntimeError("call common.start_run() or common.use_latest_run() before step_dir()")
    d = OUTPUT_DIR / RUN_ID / f"step_{n:02d}"
    if create:
        d.mkdir(parents=True, exist_ok=True)
    return d


def load_json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def dump_json(obj, path: Path) -> None:
    Path(path).write_text(
        json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def load_yaml(path: Path):
    p = Path(path)
    if not p.exists():
        return None
    return yaml.safe_load(p.read_text(encoding="utf-8"))


def dump_yaml(obj, path: Path) -> None:
    Path(path).write_text(
        yaml.safe_dump(obj, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )


# ----------------------------------------------------------------------- config
def load_config() -> dict:
    """Merge config/pipeline.yaml + config/metadata.yaml into one dict.

    structure.yaml is loaded lazily by step 03 only (it may not exist yet).
    """
    cfg = load_yaml(CONFIG_DIR / "pipeline.yaml") or {}
    meta = load_yaml(CONFIG_DIR / "metadata.yaml") or {}
    cfg["metadata"] = meta
    return cfg


def load_structure() -> dict | None:
    return load_yaml(CONFIG_DIR / "structure.yaml")


# ------------------------------------------------------------------------- misc
def get_logger(name: str) -> logging.Logger:
    # Windows consoles often default to cp1252; Vietnamese diacritics in a log
    # message or print() then crash with UnicodeEncodeError. Force UTF-8 on
    # both streams (once - reconfigure is idempotent-safe to call repeatedly).
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )
    return logging.getLogger(name)


def base_argparser(description: str) -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=description)
    ap.add_argument(
        "--run-id",
        default="",
        help="target a specific run (output/<run_id>/); default is the latest run "
             "(step 00 instead starts a NEW run unless this is given).",
    )
    ap.add_argument(
        "--limit",
        type=int,
        default=0,
        help="process at most N units (pages/chapters); 0 = all. For quick test runs.",
    )
    ap.add_argument(
        "--chapter",
        default="",
        help="restrict to one or more chapter ids, comma-separated (e.g. ch02,ch03), "
             "where applicable. Needed when a run holds multiple chapters and you want "
             "them rebuilt together in one doc_model.json, not one at a time.",
    )
    ap.add_argument("--workers", type=int, default=1, help="parallel workers where supported.")
    return ap


def nfc(text: str) -> str:
    """Normalise to Unicode NFC - required so Vietnamese diacritics compare/render
    consistently and validators don't choke on decomposed sequences."""
    return unicodedata.normalize("NFC", text)


def run(cmd: list[str], *, check: bool = True, capture: bool = False,
        stdin_text: str | None = None) -> subprocess.CompletedProcess:
    """Thin wrapper around subprocess with sane defaults and readable errors."""
    return subprocess.run(
        cmd,
        check=check,
        text=True,
        input=stdin_text,
        capture_output=capture,
        encoding="utf-8",
    )


def which_or_config(cfg_value: str | None, exe_name: str) -> str:
    """Return an explicit config path if given and existing, else bare exe name
    (resolved via PATH by subprocess)."""
    if cfg_value:
        p = Path(cfg_value)
        if p.exists():
            return str(p)
    return exe_name


def fmt_duration(seconds: float) -> str:
    seconds = int(round(max(0, seconds)))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h{m:02d}m{s:02d}s"
    if m:
        return f"{m}m{s:02d}s"
    return f"{s}s"


class Progress:
    """Per-item timing with a rolling time/item rate and ETA - so a run's log
    (and a persisted timing.csv) answer "how long will the rest of the book
    take" instead of just "still running".

    Usage:
        prog = common.Progress(len(manifest), log, "page", out / "timing.csv")
        for e in manifest:
            ... process one page ...
            prog.tick(note=f"conf {mean_c:.2f}")
        prog.close()
    """

    def __init__(self, total: int, logger: logging.Logger, label: str,
                 csv_path: Path | None = None, log_every: int = 1):
        self.total = total
        self.log = logger
        self.label = label
        self.log_every = max(1, log_every)
        self.t0 = time.time()
        self._last = self.t0
        self.n = 0
        self._writer = None
        self._fh = None
        if csv_path:
            csv_path.parent.mkdir(parents=True, exist_ok=True)
            self._fh = open(csv_path, "w", newline="", encoding="utf-8")
            self._writer = csv.writer(self._fh)
            self._writer.writerow(
                ["n", "item_seconds", "elapsed_seconds", "avg_seconds_per_item", "eta_seconds"]
            )

    def tick(self, note: str = "") -> None:
        now = time.time()
        item_s = now - self._last
        self._last = now
        self.n += 1
        elapsed = now - self.t0
        avg = elapsed / self.n
        eta = max(0, self.total - self.n) * avg

        if self._writer:
            self._writer.writerow([self.n, round(item_s, 3), round(elapsed, 3),
                                    round(avg, 3), round(eta, 3)])
            self._fh.flush()

        if self.n % self.log_every == 0 or self.n == self.total:
            extra = f"  ({note})" if note else ""
            self.log.info(
                "  %d/%d %s  |  %.2fs/%s avg  |  elapsed %s  |  eta %s%s",
                self.n, self.total, self.label, avg, self.label,
                fmt_duration(elapsed), fmt_duration(eta), extra,
            )

    def close(self) -> None:
        if self._fh:
            self._fh.close()


_CH_NUM = re.compile(r"^ch0*(\d+)$", re.I)


def chapter_label(chapter_id: str) -> str:
    """'Chuong N' derived from the id itself (ch02 -> Chuong 2), not from
    enumeration order - a chapter is often built in its own run (--chapter),
    so "the Nth book found in this run's daisy/ folder" is not its real
    chapter number. Ids that aren't chNN (e.g. "intro") use the id as-is."""
    m = _CH_NUM.match(chapter_id)
    return f"Chuong {int(m.group(1))}" if m else chapter_id


def sha256_file(path: Path) -> str:
    import hashlib

    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

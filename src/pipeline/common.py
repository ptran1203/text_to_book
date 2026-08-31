"""Shared helpers for the text_to_book DAISY pipeline.

Every step script does:

    import common
    cfg = common.load_config()
    ...
    out = common.step_dir(3)          # -> <root>/output/step_03  (created)

Step scripts are run directly (``python src/pipeline/03_structure.py``); they are
not importable as modules because their names start with a digit.  They import
this file by adding their own directory to ``sys.path`` first.
"""
from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
import unicodedata
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


# --------------------------------------------------------------------------- io
def step_dir(n: int, *, create: bool = True) -> Path:
    d = OUTPUT_DIR / f"step_{n:02d}"
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
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )
    return logging.getLogger(name)


def base_argparser(description: str) -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=description)
    ap.add_argument(
        "--limit",
        type=int,
        default=0,
        help="process at most N units (pages/chapters); 0 = all. For quick test runs.",
    )
    ap.add_argument(
        "--chapter",
        default="",
        help="restrict to a single chapter id (e.g. ch03), where applicable.",
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


def sha256_file(path: Path) -> str:
    import hashlib

    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

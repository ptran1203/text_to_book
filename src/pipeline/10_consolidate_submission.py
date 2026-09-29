"""Step 10 (cross-run) - gather every chapter's latest built submission folder
into ONE tree ready to hand in.

Chapters routinely get built across several different runs (a fix, an
extended page range, a rebuild after correcting a boundary...), so no single
output/<run_id>/step_08/ has all of them - it only has whatever that run
built. This walks config/structure.yaml's chapter list, finds each one's most
recently modified build across ALL runs, and copies them together.

Not tied to one run_id, so output goes to a fixed location:
    output/SUBMISSION/<mshv_folder>/<book_slug>-<Chapter label>/
        <book_slug>.zip
        <book_slug>_sha256sums.txt
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common

log = common.get_logger("step10")


def find_latest_build(slug: str, chapter_id: str) -> Path | None:
    label = common.chapter_label(chapter_id)
    hits = list(common.OUTPUT_DIR.glob(f"*/step_08/*/{slug}-{label}"))
    if not hits:
        return None
    return max(hits, key=lambda p: p.stat().st_mtime)


def main() -> None:
    cfg = common.load_config()
    meta = cfg.get("metadata", {})
    slug = meta.get("book_slug", "book")
    mshv_folder = "_".join(str(x) for x in meta.get("mshv", []) or ["MSHV"])

    struct = common.load_structure()
    if not struct or not struct.get("chapters"):
        sys.exit("config/structure.yaml has no chapters yet")

    dest_root = common.OUTPUT_DIR / "SUBMISSION" / mshv_folder
    if dest_root.exists():
        shutil.rmtree(dest_root)
    dest_root.mkdir(parents=True)

    missing = []
    for c in struct["chapters"]:
        cid = c["id"]
        latest = find_latest_build(slug, cid)
        if latest is None:
            missing.append(cid)
            log.warning("  %-6s  NOT BUILT YET - skipped", cid)
            continue
        shutil.copytree(latest, dest_root / latest.name)
        run_id = latest.parents[2].name
        log.info("  %-6s  %s  (from run %s)", cid, latest.name, run_id)

    log.info("done: %d/%d chapters -> %s", len(struct["chapters"]) - len(missing),
             len(struct["chapters"]), dest_root)
    if missing:
        log.warning("missing (not yet built): %s", ", ".join(missing))
        sys.exit(1)


if __name__ == "__main__":
    main()

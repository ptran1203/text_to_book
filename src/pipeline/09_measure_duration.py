"""Step 09 (cross-run report) - measure narrated-audio duration per member.

Course requirement: each member needs >= requirements.min_seconds_per_member
(default 3600s = 1h) of narrated speech. Chapters are assigned to members via
`assigned_to` in config/structure.yaml; this scans EVERY run's TTS output
(output/*/step_04/chapters/<id>/timings.json) - not just the latest run - so
it works regardless of how many separate runs were used to build different
chapters. For a chapter built more than once, the most recent run wins.

Not tied to one run_id (it reports across all of them), so output goes to a
fixed location rather than output/<run_id>/:
    output/duration_report.json
    output/duration_report.md
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common

log = common.get_logger("step09")


def fmt_hms(seconds: float) -> str:
    return common.fmt_duration(seconds)


def find_latest_timings(chapter_id: str) -> tuple[str, dict] | tuple[None, None]:
    """Most recent run that has timings for this chapter - by file mtime, NOT
    by sorting run_id strings: a custom run_id (e.g. "final", "ch04full") does
    not sort chronologically against a timestamp one or against each other, so
    string-sorting silently picked a stale build here once (caught by hand -
    ch04's real 58min rebuild lost to a stale 16min one just by string order)."""
    hits = common.OUTPUT_DIR.glob(f"*/step_04/chapters/{chapter_id}/timings.json")
    hits = sorted(hits, key=lambda p: p.stat().st_mtime)
    if not hits:
        return None, None
    latest = hits[-1]
    # latest = output/<run_id>/step_04/chapters/<chapter_id>/timings.json
    #            parents:      [3]       [2]        [1]           [0]
    run_id = latest.parents[3].name
    return run_id, common.load_json(latest)


def main() -> None:
    cfg = common.load_config()
    required = float(cfg.get("requirements", {}).get("min_seconds_per_member", 3600))
    struct = common.load_structure()
    if not struct:
        sys.exit("config/structure.yaml missing")
    chapters = struct.get("chapters", [])
    if not chapters:
        sys.exit("config/structure.yaml has no chapters yet")

    per_chapter = []
    per_member: dict[str, float] = {}
    for c in chapters:
        cid = c["id"]
        member = c.get("assigned_to") or "(unassigned)"
        run_id, timings = find_latest_timings(cid)
        secs = float(timings.get("_total", 0.0)) if timings else 0.0
        per_chapter.append(dict(chapter=cid, title=c.get("title", ""), assigned_to=member,
                                 run_id=run_id, seconds=round(secs, 1)))
        per_member[member] = per_member.get(member, 0.0) + secs
        status = "not built yet" if run_id is None else f"run {run_id}"
        log.info("  %-6s  %-12s  %8s  (%s)", cid, member, fmt_hms(secs), status)

    lines = ["# Narrated-audio duration report\n",
             f"_Required per member: {fmt_hms(required)}_\n",
             "## Per member", "| member | chapters | total | required | status |",
             "|---|---|---|---|---|"]
    all_ok = True
    for member in sorted(per_member):
        secs = per_member[member]
        chs = [pc["chapter"] for pc in per_chapter if pc["assigned_to"] == member]
        ok = secs >= required
        all_ok &= ok
        status = "OK" if ok else f"short by {fmt_hms(required - secs)}"
        lines.append(f"| {member} | {', '.join(chs)} | {fmt_hms(secs)} | {fmt_hms(required)} | {status} |")

    lines += ["", "## Per chapter", "| chapter | assigned to | title | duration | source run |",
              "|---|---|---|---|---|"]
    for pc in per_chapter:
        lines.append(f"| {pc['chapter']} | {pc['assigned_to']} | {pc['title']} | "
                     f"{fmt_hms(pc['seconds'])} | {pc['run_id'] or '-'} |")

    grand_total = sum(per_member.values())
    lines += ["", f"**Grand total: {fmt_hms(grand_total)}** across {len(per_member)} member(s), "
                  f"required {fmt_hms(required * len(per_member))} ({len(per_member)} x {fmt_hms(required)})"]

    common.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (common.OUTPUT_DIR / "duration_report.md").write_text("\n".join(lines), encoding="utf-8")
    common.dump_json(dict(required_seconds=required, per_member=per_member,
                          per_chapter=per_chapter, grand_total_seconds=round(grand_total, 1)),
                     common.OUTPUT_DIR / "duration_report.json")

    print("\n".join(lines))
    log.info("report -> %s", common.OUTPUT_DIR / "duration_report.md")
    if not all_ok:
        sys.exit(1)


if __name__ == "__main__":
    main()

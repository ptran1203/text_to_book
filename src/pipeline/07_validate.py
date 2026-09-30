"""Step 07 - validate each assembled DAISY 3 book.

Internal consistency checks (always) + DAISY Pipeline 2 daisy3-validator
(if `dp2` is on PATH / configured).  Optionally runs a daisy3-to-daisy3
mastering pass into output/step_07/mastered/<id>.

Checks:
  * every SMIL  <text src="book.dtbook.xml#ID">  ->  ID exists in the DTBook
  * every SMIL  <audio src="audio/x.mp3">        ->  file exists
  * every NCX   <content src="book.smil#PAR">    ->  PAR exists in the SMIL
  * OPF manifest <-> files on disk agree (mp3s)
  * NCX totalPageCount / maxPageNumber match the pageList
  * OPF dtb:totalTime ~= sum of clip durations (+-3s)
  * dc:Identifier identical across all chapter books

Outputs
    output/step_07/report.txt
    output/step_07/<id>.json
    output/step_07/mastered/<id>/...        (if run_mastering)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common

log = common.get_logger("step07")

_ID = re.compile(r'\bid="([^"]+)"')
_TEXT_SRC = re.compile(r'<text\s+src="book\.dtbook\.xml#([^"]+)"')
_AUDIO_SRC = re.compile(r'<audio\s+src="([^"]+)"')
_CLIPEND = re.compile(r'clipEnd="([\d.]+)s"')
_NCX_CONTENT = re.compile(r'<content\s+src="book\.smil#([^"]+)"')
_META = re.compile(r'<meta\s+name="([^"]+)"\s+content="([^"]*)"')
_PAGE_TARGET = re.compile(r'<pageTarget\b[^>]*>')
_PAGE_VALUE = re.compile(r'value="(\d+)"')
_OPF_MP3 = re.compile(r'href="audio/([^"]+\.mp3)"')
_DC_ID = re.compile(r'<dc:Identifier[^>]*>([^<]+)</dc:Identifier>')


def check_book(bdir: Path) -> dict:
    errs, warns = [], []
    dt = (bdir / "book.dtbook.xml").read_text(encoding="utf-8")
    sm = (bdir / "book.smil").read_text(encoding="utf-8")
    ncx = (bdir / "book.ncx").read_text(encoding="utf-8")
    opf = (bdir / "book.opf").read_text(encoding="utf-8")

    dt_ids = set(_ID.findall(dt))
    sm_ids = set(_ID.findall(sm))

    for ref in _TEXT_SRC.findall(sm):
        if ref not in dt_ids:
            errs.append(f"SMIL text id not in DTBook: {ref}")
    for a in _AUDIO_SRC.findall(sm):
        if not (bdir / a).exists():
            errs.append(f"SMIL audio file missing: {a}")
    for par in _NCX_CONTENT.findall(ncx):
        if par not in sm_ids:
            errs.append(f"NCX points at missing SMIL par: {par}")

    disk_mp3 = {p.name for p in (bdir / "audio").glob("*.mp3")}
    opf_mp3 = set(_OPF_MP3.findall(opf))
    for m in disk_mp3 - opf_mp3:
        warns.append(f"mp3 on disk not in OPF manifest: {m}")
    for m in opf_mp3 - disk_mp3:
        errs.append(f"OPF manifest lists missing mp3: {m}")

    ncx_meta = dict(_META.findall(ncx))
    n_pt = len(_PAGE_TARGET.findall(ncx))
    values = [int(v) for v in _PAGE_VALUE.findall(ncx)]
    if int(ncx_meta.get("dtb:totalPageCount", -1)) != n_pt:
        errs.append(f"NCX totalPageCount {ncx_meta.get('dtb:totalPageCount')} != {n_pt} pageTargets")
    if values and int(ncx_meta.get("dtb:maxPageNumber", -1)) != max(values):
        errs.append(f"NCX maxPageNumber {ncx_meta.get('dtb:maxPageNumber')} != {max(values)}")

    clip_total = sum(float(x) for x in _CLIPEND.findall(sm))
    opf_meta = dict(_META.findall(opf))
    tt = opf_meta.get("dtb:totalTime", "0:00:00")
    h, m, s = (int(x) for x in tt.split(":"))
    opf_secs = h * 3600 + m * 60 + s
    if abs(opf_secs - clip_total) > 3:
        warns.append(f"OPF totalTime {tt} ({opf_secs}s) vs summed clips {clip_total:.1f}s")

    dc_ids = _DC_ID.findall(opf)
    return dict(book=bdir.name, errors=errs, warnings=warns,
                dc_identifier=dc_ids[0] if dc_ids else "",
                clip_total_seconds=round(clip_total, 1))


def run_dp2(dp2: str, opf: Path, report_dir: Path) -> str:
    try:
        cp = common.run([dp2, "daisy3-validator", f"--input={opf}"],
                        check=False, capture=True)
        return (cp.stdout or "") + (cp.stderr or "")
    except FileNotFoundError:
        return "DP2 not found on PATH - skipped (set step_07_validate.dp2)"


def run_mastering(dp2: str, src_dir: Path, dst_dir: Path) -> str:
    try:
        dst_dir.mkdir(parents=True, exist_ok=True)
        cp = common.run(
            [dp2, "daisy3-to-daisy3", f"--input={src_dir / 'book.opf'}",
             f"--output={dst_dir}"],
            check=False, capture=True,
        )
        return (cp.stdout or "") + (cp.stderr or "")
    except FileNotFoundError:
        return "DP2 not found - mastering skipped"


def main() -> None:
    args = common.base_argparser(__doc__).parse_args()
    run_id = common.use_latest_run(args.run_id)
    log.info("run_id: %s", run_id)
    cfg = common.load_config()
    vcfg = cfg.get("step_07_validate", {})
    dp2 = common.which_or_config(vcfg.get("dp2"), "dp2")

    daisy = common.step_dir(6, create=False) / "daisy"
    books = sorted(p for p in daisy.iterdir() if p.is_dir()) if daisy.exists() else []
    if args.chapter:
        wanted = set(args.chapter.split(","))
        books = [b for b in books if b.name in wanted]
    if args.limit:
        books = books[: args.limit]
    if not books:
        sys.exit("no assembled books - run step 06 first")

    out = common.step_dir(7)
    lines, all_ids, hard_fail = [], set(), False
    for b in books:
        r = check_book(b)
        all_ids.add(r["dc_identifier"])
        common.dump_json(r, out / f"{b.name}.json")
        lines.append(f"== {b.name} ==")
        lines += [f"  ERROR  {e}" for e in r["errors"]]
        lines += [f"  warn   {w}" for w in r["warnings"]]
        if not r["errors"]:
            lines.append("  internal checks: OK")
        hard_fail |= bool(r["errors"])

        if vcfg.get("run_validator", True):
            dp2_out = run_dp2(dp2, b / "book.opf", out)
            (out / f"{b.name}.dp2.txt").write_text(dp2_out, encoding="utf-8")
            lines.append(f"  dp2: see {b.name}.dp2.txt")
            if re.search(r"\berror\b", dp2_out, re.I):
                hard_fail = True
        if vcfg.get("run_mastering", False):
            mo = run_mastering(dp2, b, out / "mastered" / b.name)
            (out / f"{b.name}.master.txt").write_text(mo, encoding="utf-8")

    if len(all_ids) > 1:
        lines.append(f"\nERROR  dc:Identifier differs across chapters: {sorted(all_ids)}")
        hard_fail = True
    else:
        lines.append(f"\nshared dc:Identifier: {next(iter(all_ids), '(none)')}")

    (out / "report.txt").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    log.info("report -> %s", out / "report.txt")

    if hard_fail and vcfg.get("fail_on_validator_error", True):
        sys.exit("validation failed - see report.txt")


if __name__ == "__main__":
    main()

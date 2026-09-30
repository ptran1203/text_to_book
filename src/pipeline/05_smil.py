"""Step 05 - build one DAISY 3 SMIL file per chapter.

Pairs every DTBook leaf id with its audio clip.  Because each sentence is its own
MP3, clipBegin is always 0s and clipEnd is the measured duration.  <pagenum>s
become text-only <par>s (players announce them; step 07 mastering can add TTS).

Outputs
    output/step_05/chapters/<id>/book.smil
    output/step_05/chapters/<id>/nav.json    heading + page -> par id, total seconds
"""
from __future__ import annotations

import sys
from pathlib import Path
from xml.sax.saxutils import quoteattr

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common

log = common.get_logger("step05")

SMIL_DOCTYPE = (
    '<!DOCTYPE smil PUBLIC "-//NISO//DTD dtbsmil 2005-2//EN" '
    '"http://www.daisy.org/z3986/2005/dtbsmil-2005-2.dtd">'
)


def hms(seconds: float) -> str:
    s = int(round(seconds))
    return f"{s // 3600}:{(s % 3600) // 60:02d}:{s % 60:02d}"


def build_smil(chapter: dict, timings: dict, uid: str):
    dt = "book.dtbook.xml"
    pars = []
    nav = {"heading": None, "pages": [], "par_count": 0}
    n = 0

    def par(ref_id, cls, audio=None):
        nonlocal n
        n += 1
        pid = f"par_{n:04d}"
        lines = [f'      <par id="{pid}" class="{cls}">',
                 f'        <text src={quoteattr(dt + "#" + ref_id)}/>']
        if audio:
            lines.append(
                f'        <audio src={quoteattr(audio["file"])} '
                f'clipBegin="0s" clipEnd="{audio["dur"]}s"/>'
            )
        lines.append("      </par>")
        pars.append("\n".join(lines))
        return pid

    hid = f'{chapter["id"]}_h'
    nav["heading"] = {"ref": hid, "par": par(hid, "title", timings.get(hid))}

    for b in chapter["blocks"]:
        if b["type"] == "pagenum":
            pid = par(b["id"], "pagenum", timings.get(b["id"]))
            nav["pages"].append({"printed": b["printed"], "ref": b["id"], "par": pid})
        elif b["type"] == "p":
            for s in b["sents"]:
                if s["text"].strip():
                    par(s["id"], "sent", timings.get(s["id"]))

    nav["par_count"] = n
    total = timings.get("_total", 0.0)
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n' + SMIL_DOCTYPE + "\n"
        '<smil xmlns="http://www.w3.org/2001/SMIL20/">\n'
        "  <head>\n"
        f'    <meta name="dtb:uid" content={quoteattr(uid)}/>\n'
        f'    <meta name="dtb:totalElapsedTime" content="0:00:00"/>\n'
        '    <meta name="dtb:generator" content="text_to_book pipeline"/>\n'
        "  </head>\n"
        "  <body>\n"
        f'    <seq id="{chapter["id"]}_seq" dur="{round(total, 3)}s">\n'
        + "\n".join(pars) +
        "\n    </seq>\n"
        "  </body>\n"
        "</smil>\n"
    )
    nav["total_seconds"] = round(total, 3)
    return xml, nav


def main() -> None:
    args = common.base_argparser(__doc__).parse_args()
    run_id = common.use_latest_run(args.run_id)
    log.info("run_id: %s", run_id)
    cfg = common.load_config()
    meta = cfg.get("metadata", {})

    model = common.load_json(common.step_dir(3, create=False) / "doc_model.json")
    chapters = model["chapters"]
    if args.chapter:
        wanted = set(args.chapter.split(","))
        chapters = [c for c in chapters if c["id"] in wanted]
    if args.limit:
        chapters = chapters[: args.limit]

    step4 = common.step_dir(4, create=False)
    out = common.step_dir(5)
    for ch in chapters:
        tpath = step4 / "chapters" / ch["id"] / "timings.json"
        if not tpath.exists():
            sys.exit(f"missing timings for {ch['id']} - run step 04 first")
        timings = common.load_json(tpath)
        uid = f'{meta.get("isbn") or meta.get("book_slug", "book")}-{ch["id"]}'
        xml, nav = build_smil(ch, timings, uid)

        cdir = out / "chapters" / ch["id"]
        cdir.mkdir(parents=True, exist_ok=True)
        (cdir / "book.smil").write_text(xml, encoding="utf-8")
        common.dump_json(nav, cdir / "nav.json")
        log.info("  %s  %d pars  %s", ch["id"], nav["par_count"], hms(nav["total_seconds"]))

    log.info("done -> %s", out)


if __name__ == "__main__":
    main()

"""Step 03 - document structure + DTBook XML  (MANUAL REVIEW CHECKPOINT).

Two modes:

  python 03_structure.py --detect
      Heuristically finds chapter headings (glyph height from step 01's line
      boxes, ALL-CAPS lines, and the heading regex) and writes
      config/structure.yaml as a TEMPLATE for you to correct, plus
      output/step_03/review.md.

  python 03_structure.py
      Reads config/structure.yaml, builds the document model and one valid
      DTBook 2005-3 file per chapter.

Outputs (build mode)
    output/step_03/chapters/<id>/book.dtbook.xml
    output/step_03/doc_model.json
    output/step_03/review.md
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common

log = common.get_logger("step03")

_SENT = re.compile(r"(.+?(?:[.!?…]+[”’\")]?|$))(?:\s+|$)", re.S)


# ---------------------------------------------------------------- detect mode
def page_lines(path: Path):
    """(text, height) for every recognised line on a page, from step 01's json."""
    for rec in common.load_json(path):
        text = rec.get("text", "").strip()
        if text:
            yield text, rec["height"]


def detect(cfg) -> None:
    scfg = cfg.get("step_03_structure", {})
    ratio = float(scfg.get("heading_height_ratio", 1.35))
    hrx = re.compile(scfg.get("heading_regex", r"^(PHẦN|Phần|CHƯƠNG|Chương|Chapter|PART)\b"))
    offset = int(scfg.get("page_offset", 0))

    ldir = common.step_dir(1, create=False) / "lines"
    line_files = sorted(ldir.glob("p*.json"))
    if not line_files:
        sys.exit("no line data - run step 01 first")

    candidates = []
    for f in line_files:
        idx = int(f.stem[1:])
        rows = list(page_lines(f))
        if not rows:
            continue
        heights = sorted(h for _, h in rows)
        median = heights[len(heights) // 2] or 1
        for text, h in rows:
            big = h >= ratio * median
            caps = text == text.upper() and len(re.sub(r"[^A-Za-zÀ-ỹ]", "", text)) >= 3
            if (big or caps or hrx.search(text)) and len(text) <= 90:
                candidates.append((idx, text, h, round(h / median, 2)))
                break  # one heading per page is plenty for a seed

    chapters = []
    for i, (idx, text, h, rel) in enumerate(candidates, 1):
        chapters.append(dict(
            id=f"ch{i:02d}", title=text, level=1,
            start_page=idx, printed_start=idx + offset,
        ))

    first = chapters[0]["start_page"] if chapters else 1
    struct = dict(
        page_offset=offset,
        front_matter=dict(pages=[1, max(1, first - 1)]),
        chapters=chapters,
        back_matter=dict(pages=[]),
    )
    common.dump_yaml(struct, common.CONFIG_DIR / "structure.yaml")

    out = common.step_dir(3)
    lines = ["# Detected chapters (REVIEW & EDIT config/structure.yaml)\n",
             f"_{len(chapters)} candidates from {len(line_files)} pages_\n",
             "| id | img page | printed | rel height | title |",
             "|----|---------|---------|-----------|-------|"]
    for c, (idx, text, h, rel) in zip(chapters, candidates):
        lines.append(f"| {c['id']} | {idx} | {c['printed_start']} | {rel} | {text} |")
    (out / "review.md").write_text("\n".join(lines), encoding="utf-8")
    log.info("wrote config/structure.yaml with %d chapters + review.md - EDIT then rerun without --detect",
             len(chapters))


# ----------------------------------------------------------------- build mode
def read_pages() -> dict[int, str]:
    pdir = common.step_dir(2, create=False) / "pages"
    return {int(f.stem[1:]): f.read_text(encoding="utf-8") for f in sorted(pdir.glob("p*.txt"))}


def split_sentences(para: str) -> list[str]:
    para = para.strip()
    if not para:
        return []
    out = [s.strip() for s in _SENT.findall(para) if s.strip()]
    return out or [para]


def build_chapter_model(ch: dict, pages: dict[int, str], end: int, offset: int,
                        split_sent: bool) -> dict:
    cid = ch["id"]
    start = int(ch["start_page"])
    blocks = [dict(type="h1", id=f"{cid}_h", text=common.nfc(ch["title"].strip()))]
    page_list = []
    pno = 0
    for img in range(start, end + 1):
        printed = str(img + offset)
        page_list.append(dict(image_index=img, printed=printed))
        blocks.append(dict(type="pagenum", id=f"{cid}_page_{img:04d}", printed=printed))
        text = pages.get(img, "")
        for para in [p for p in text.split("\n\n") if p.strip()]:
            pno += 1
            pid = f"{cid}_p{pno:04d}"
            sents = split_sentences(para) if split_sent else [para.strip()]
            blocks.append(dict(
                type="p", id=pid,
                sents=[dict(id=f"{pid}_s{j:02d}", text=common.nfc(s))
                       for j, s in enumerate(sents, 1)],
            ))
    return dict(id=cid, title=common.nfc(ch["title"].strip()), level=int(ch.get("level", 1)),
                start_page=start, end_page=end, pages=page_list, blocks=blocks)


DTBOOK_DOCTYPE = (
    '<!DOCTYPE dtbook PUBLIC "-//NISO//DTD dtbook 2005-3//EN" '
    '"http://www.daisy.org/z3986/2005/dtbook-2005-3.dtd">'
)


def dtbook_xml(chapter: dict, meta: dict, uid: str) -> str:
    def m(name, content):
        return f'    <meta name={quoteattr(name)} content={quoteattr(content)}/>'

    creators = ", ".join(c["name"] for c in meta.get("creators", []) if c.get("name"))
    pairs = [
        ("dtb:uid", uid),
        ("dc:Title", chapter["title"]),
        ("dc:Creator", creators),
        ("dc:Language", meta.get("language", "vi")),
        ("dc:Publisher", meta.get("publisher", "") or ""),
        ("dc:Identifier", meta.get("isbn", "") or uid),
        ("dc:Date", str(meta.get("pub_year", "") or "")),
    ]
    head = [m(k, v) for k, v in pairs if v]
    body = ['  <bodymatter>', f'    <level1 id={quoteattr(chapter["id"])}>']
    body.append(f'      <h1 id={quoteattr(chapter["id"] + "_h")}>{escape(chapter["title"])}</h1>')
    for b in chapter["blocks"]:
        if b["type"] == "h1":
            continue
        if b["type"] == "pagenum":
            body.append(
                f'      <pagenum id={quoteattr(b["id"])} page="normal">{escape(b["printed"])}</pagenum>'
            )
        elif b["type"] == "p":
            inner = "".join(
                f'<sent id={quoteattr(s["id"])}>{escape(s["text"])}</sent>'
                + ("" if k == len(b["sents"]) else " ")
                for k, s in enumerate(b["sents"], 1)
            )
            body.append(f'      <p id={quoteattr(b["id"])}>{inner}</p>')
    body += ['    </level1>', '  </bodymatter>']

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        + DTBOOK_DOCTYPE + "\n"
        + '<dtbook xmlns="http://www.daisy.org/z3986/2005/dtbook/" version="2005-3" xml:lang='
        + quoteattr(meta.get("language", "vi")) + ">\n"
        + "  <head>\n" + "\n".join(head) + "\n  </head>\n"
        + "  <book>\n" + "\n".join(body) + "\n  </book>\n"
        + "</dtbook>\n"
    )


def main() -> None:
    ap = common.base_argparser(__doc__)
    ap.add_argument("--detect", action="store_true", help="seed config/structure.yaml and exit")
    args = ap.parse_args()
    run_id = common.use_latest_run(args.run_id)
    log.info("run_id: %s", run_id)
    cfg = common.load_config()

    if args.detect:
        detect(cfg)
        return

    struct = common.load_structure()
    if not struct:
        sys.exit("config/structure.yaml missing - run:  python src/pipeline/03_structure.py --detect")

    scfg = cfg.get("step_03_structure", {})
    offset = int(struct.get("page_offset", scfg.get("page_offset", 0)))
    split_sent = bool(scfg.get("sentence_split", True))
    meta = cfg.get("metadata", {})
    pages = read_pages()
    if not pages:
        sys.exit("no cleaned pages - run step 02 first")
    last_img = max(pages)

    chapters = struct.get("chapters", [])
    if args.chapter:
        wanted = set(args.chapter.split(","))
        chapters = [c for c in chapters if c["id"] in wanted]
    if args.limit:
        chapters = chapters[: args.limit]
    if not chapters:
        sys.exit("no chapters selected")

    starts = [int(c["start_page"]) for c in struct.get("chapters", [])]
    out = common.step_dir(3)
    (out / "chapters").mkdir(exist_ok=True)

    model = dict(book=dict(
        title=meta.get("title", ""), isbn=meta.get("isbn", ""),
        language=meta.get("language", "vi"),
        creators=meta.get("creators", []), publisher=meta.get("publisher", ""),
    ), chapters=[])

    review = ["# Chapter build summary\n", "| id | pages | paras | sentences | title |",
              "|----|-------|-------|-----------|-------|"]
    for c in chapters:
        s = int(c["start_page"])
        nxt = [x for x in starts if x > s]
        end = (min(nxt) - 1) if nxt else last_img
        end = int(c.get("end_page", end))

        # A chapter whose page range doesn't overlap this run's cleaned text at
        # all is a mismatch (e.g. structure.yaml built for pages 17-40, but this
        # run's step 00/01/02 only covered a different range) - refuse to
        # silently build an empty-content "book" for it.
        wanted = range(s, end + 1)
        missing = [img for img in wanted if img not in pages]
        if len(missing) == len(wanted):
            sys.exit(
                f"chapter {c['id']}: none of pages {s}-{end} exist in this run's cleaned "
                f"text (this run only has pages {min(pages)}-{max(pages)}). Extract/OCR "
                f"the chapter's actual pages first, e.g.:\n"
                f"  python src/pipeline/00_extract_pages.py --start {s} --end {end}\n"
                f"  python src/pipeline/01_ocr.py\n"
                f"  python src/pipeline/02_clean_text.py"
            )
        if missing:
            log.warning("  %s: %d/%d pages missing from this run's OCR %s - text will have gaps",
                        c["id"], len(missing), len(wanted), missing[:5])

        cm = build_chapter_model(c, pages, end, offset, split_sent)

        n_p = sum(1 for b in cm["blocks"] if b["type"] == "p")
        n_s = sum(len(b["sents"]) for b in cm["blocks"] if b["type"] == "p")
        if n_p == 0:
            sys.exit(f"chapter {c['id']} has ZERO paragraphs after building (pages {s}-{end}) - "
                     f"refusing to write an empty book. Check the chapter's page range.")

        model["chapters"].append(cm)
        cdir = out / "chapters" / cm["id"]
        cdir.mkdir(parents=True, exist_ok=True)
        uid = f'{meta.get("isbn") or meta.get("book_slug", "book")}-{cm["id"]}'
        (cdir / "book.dtbook.xml").write_text(dtbook_xml(cm, meta, uid), encoding="utf-8")

        review.append(f"| {cm['id']} | {s}-{end} | {n_p} | {n_s} | {cm['title']} |")
        log.info("  %s  pages %d-%d  %d paras  %d sentences", cm["id"], s, end, n_p, n_s)

    common.dump_json(model, out / "doc_model.json")
    (out / "review.md").write_text("\n".join(review), encoding="utf-8")
    log.info("done: %d chapters -> %s", len(model["chapters"]), out)


if __name__ == "__main__":
    main()

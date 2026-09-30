"""Step 00 - PDF -> one image per page.

data/book.pdf is a scanned book (1-bit page images, no embedded text).  For each
page we either lift the embedded full-page scan losslessly, or - if the page is
not a single image - rasterise it at render_dpi.

Use --start/--end to jump straight to a page range (e.g. skip past front matter
into a chapter) instead of always extracting from page 1. Every step downstream
just processes whatever pages/manifest step 00 produced for this run, so this
is the only place a range needs specifying.

Outputs
    output/<run_id>/step_00/pages/p0001.png ...   (p0001 = the PDF's page 1, even
                                                    with --start > 1 - filenames
                                                    are absolute PDF page numbers)
    output/<run_id>/step_00/cover.<ext>           (PDF page 1, only when included)
    output/<run_id>/step_00/manifest.json         [{index, file, width, height, source, dpi}]
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common

import fitz  # PyMuPDF

log = common.get_logger("step00")


def page_is_single_fullpage_image(page: "fitz.Page") -> tuple[bool, int | None]:
    imgs = page.get_images(full=True)
    if len(imgs) != 1:
        return False, None
    # Is that image roughly the whole page?
    xref = imgs[0][0]
    rects = page.get_image_rects(xref)
    if not rects:
        return False, None
    r = rects[0]
    pw, ph = page.rect.width, page.rect.height
    covers = (r.width >= 0.9 * pw) and (r.height >= 0.9 * ph)
    return covers, xref


def main() -> None:
    ap = common.base_argparser(__doc__)
    ap.add_argument("--start", type=int, default=1,
                     help="first PDF page to extract, 1-based (default 1)")
    ap.add_argument("--end", type=int, default=0,
                     help="last PDF page to extract, inclusive (default: to the end, "
                          "or --start + --limit - 1 if --limit is given)")
    args = ap.parse_args()
    run_id = common.start_run(args.run_id)
    cfg = common.load_config()
    scfg = cfg.get("step_00_extract", {})
    dpi = int(scfg.get("render_dpi", 300))
    prefer_native = bool(scfg.get("prefer_native_images", True))
    rendered_ext = scfg.get("image_format", "png")

    src = common.ROOT / cfg.get("source_pdf", "data/book.pdf")
    if not src.exists():
        sys.exit(f"source pdf not found: {src}")

    out = common.step_dir(0)
    pages_dir = out / "pages"
    pages_dir.mkdir(exist_ok=True)

    doc = fitz.open(src)
    start = max(1, args.start)
    if args.end:
        end = args.end
    elif args.limit:
        end = start + args.limit - 1
    else:
        end = doc.page_count
    end = min(end, doc.page_count)
    if start > end:
        sys.exit(f"--start {start} is past --end {end} (PDF has {doc.page_count} pages)")

    log.info("run_id: %s", run_id)
    log.info("PDF has %d pages; extracting %d-%d (%d pages)", doc.page_count, start, end, end - start + 1)

    manifest = []
    for idx in range(start, end + 1):
        page = doc[idx - 1]
        native_ok = False
        if prefer_native:
            native_ok, xref = page_is_single_fullpage_image(page)
        if native_ok:
            info = doc.extract_image(xref)
            ext = info["ext"]
            fname = f"p{idx:04d}.{ext}"
            (pages_dir / fname).write_bytes(info["image"])
            entry = dict(
                index=idx, file=f"pages/{fname}", width=info["width"],
                height=info["height"], source="native", dpi=None,
            )
        else:
            pix = page.get_pixmap(dpi=dpi, colorspace=fitz.csGRAY)
            fname = f"p{idx:04d}.{rendered_ext}"
            pix.save(pages_dir / fname)
            entry = dict(
                index=idx, file=f"pages/{fname}", width=pix.width,
                height=pix.height, source="rendered", dpi=dpi,
            )
        manifest.append(entry)

        if idx == 1:  # keep the cover in whatever form it is
            cover_src = pages_dir / Path(entry["file"]).name
            (out / f"cover{cover_src.suffix}").write_bytes(cover_src.read_bytes())

        if idx % 25 == 0 or idx == end:
            log.info("  %d/%d (page %d of %d-%d)", idx - start + 1, end - start + 1, idx, start, end)

    common.dump_json(manifest, out / "manifest.json")
    native = sum(1 for e in manifest if e["source"] == "native")
    log.info("done: %d pages (%d native, %d rendered) -> %s",
             len(manifest), native, len(manifest) - native, out)


if __name__ == "__main__":
    main()

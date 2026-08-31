"""Step 00 - PDF -> one image per page.

data/book.pdf is a scanned book (1-bit page images, no embedded text).  For each
page we either lift the embedded full-page scan losslessly, or - if the page is
not a single image - rasterise it at render_dpi.

Outputs
    output/step_00/pages/p0001.png ...
    output/step_00/cover.<ext>          (page 1, kept in original encoding)
    output/step_00/manifest.json        [{index, file, width, height, source, dpi}]
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
    args = ap.parse_args()
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
    n = doc.page_count
    if args.limit:
        n = min(n, args.limit)
    log.info("PDF has %d pages; extracting %d", doc.page_count, n)

    manifest = []
    for i in range(n):
        page = doc[i]
        idx = i + 1
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

        if idx % 25 == 0 or idx == n:
            log.info("  %d/%d", idx, n)

    common.dump_json(manifest, out / "manifest.json")
    native = sum(1 for e in manifest if e["source"] == "native")
    log.info("done: %d pages (%d native, %d rendered) -> %s",
             len(manifest), native, len(manifest) - native, out)


if __name__ == "__main__":
    main()

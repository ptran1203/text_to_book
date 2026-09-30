"""Step 06 - assemble a complete DAISY 3 book per chapter.

Copies the DTBook + SMIL + MP3s into one folder and generates the NCX
(navMap from the heading, pageList from <pagenum>s) and the OPF package
(manifest + Dublin Core; dc:Identifier / ISBN is shared across chapters).

Outputs
    output/step_06/daisy/<id>/book.opf
    output/step_06/daisy/<id>/book.ncx
    output/step_06/daisy/<id>/book.dtbook.xml
    output/step_06/daisy/<id>/book.smil
    output/step_06/daisy/<id>/audio/*.mp3
    output/step_06/daisy/<id>/images/cover.*        (if a cover was extracted)
"""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common

log = common.get_logger("step06")

NCX_DOCTYPE = ('<!DOCTYPE ncx PUBLIC "-//NISO//DTD ncx 2005-1//EN" '
               '"http://www.daisy.org/z3986/2005/ncx-2005-1.dtd">')
OPF_DOCTYPE = ('<!DOCTYPE package PUBLIC "+//ISBN 0-9673008-1-9//DTD OEB 1.2 Package//EN" '
               '"http://openebook.org/dtds/oeb-1.2/oebpkg12.dtd">')
_MIME = {".mp3": "audio/mpeg", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
         ".png": "image/png"}


def hms(seconds: float) -> str:
    s = int(round(seconds))
    return f"{s // 3600}:{(s % 3600) // 60:02d}:{s % 60:02d}"


def _order_key(par_id: str) -> int:
    m = re.search(r"(\d+)", par_id)
    return int(m.group(1)) if m else 0


def build_ncx(chapter, nav, meta, uid) -> str:
    creators = ", ".join(c["name"] for c in meta.get("creators", []) if c.get("name"))
    pages = nav["pages"]
    numeric = [int(p["printed"]) for p in pages if p["printed"].isdigit()]
    max_page = max(numeric) if numeric else 0

    targets = [("nav", nav["heading"])] + [("page", p) for p in pages]
    targets.sort(key=lambda t: _order_key(t[1]["par"]))

    nav_pts, page_tgts = [], []
    for order, (kind, t) in enumerate(targets, 1):
        src = f'book.smil#{t["par"]}'
        if kind == "nav":
            nav_pts.append(
                f'    <navPoint id="navp_1" class="level1" playOrder="{order}">\n'
                f'      <navLabel><text>{escape(chapter["title"])}</text></navLabel>\n'
                f'      <content src={quoteattr(src)}/>\n'
                f'    </navPoint>'
            )
        else:
            v = t["printed"]
            page_tgts.append(
                f'    <pageTarget id="pt_{order}" type="normal" '
                f'{"value=" + quoteattr(v) + " " if v.isdigit() else ""}playOrder="{order}">\n'
                f'      <navLabel><text>{escape(v)}</text></navLabel>\n'
                f'      <content src={quoteattr(src)}/>\n'
                f'    </pageTarget>'
            )

    page_list = ""
    if page_tgts:
        page_list = ('  <pageList id="pages">\n' + "\n".join(page_tgts) + "\n  </pageList>\n")

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n' + NCX_DOCTYPE + "\n"
        '<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1" xml:lang='
        + quoteattr(meta.get("language", "vi")) + ">\n"
        "  <head>\n"
        f'    <meta name="dtb:uid" content={quoteattr(uid)}/>\n'
        '    <meta name="dtb:depth" content="1"/>\n'
        f'    <meta name="dtb:totalPageCount" content="{len(pages)}"/>\n'
        f'    <meta name="dtb:maxPageNumber" content="{max_page}"/>\n'
        '    <meta name="dtb:generator" content="text_to_book pipeline"/>\n'
        "  </head>\n"
        f'  <docTitle><text>{escape(chapter["title"])}</text></docTitle>\n'
        f'  <docAuthor><text>{escape(creators)}</text></docAuthor>\n'
        '  <navMap>\n' + "\n".join(nav_pts) + "\n  </navMap>\n"
        + page_list +
        "</ncx>\n"
    )


def build_opf(chapter, meta, uid, audio_files, cover_name, total_seconds) -> str:
    dc = []
    title = chapter["title"]
    dc.append(f'      <dc:Title>{escape(title)}</dc:Title>')
    for c in meta.get("creators", []):
        if c.get("name"):
            role = c.get("role", "aut")
            dc.append(f'      <dc:Creator role={quoteattr(role)}>{escape(c["name"])}</dc:Creator>')
    dc.append(f'      <dc:Language>{escape(meta.get("language", "vi"))}</dc:Language>')
    isbn = meta.get("isbn", "") or ""
    if isbn:
        # id="uid" goes on dc:Identifier (what <package unique-identifier="uid">
        # points at); dc:Source repeats the ISBN too - the course's submission
        # form/checker expects it there specifically.
        dc.append(f'      <dc:Identifier id="uid" scheme="ISBN">{escape(isbn)}</dc:Identifier>')
        dc.append(f'      <dc:Source>{escape(isbn)}</dc:Source>')
    else:
        dc.append(f'      <dc:Identifier id="uid">{escape(uid)}</dc:Identifier>')
    if meta.get("publisher"):
        dc.append(f'      <dc:Publisher>{escape(meta["publisher"])}</dc:Publisher>')
    if meta.get("pub_year"):
        dc.append(f'      <dc:Date>{escape(str(meta["pub_year"]))}</dc:Date>')
    if meta.get("subject"):
        dc.append(f'      <dc:Subject>{escape(meta["subject"])}</dc:Subject>')
    if meta.get("description"):
        dc.append(f'      <dc:Description>{escape(str(meta["description"]).strip())}</dc:Description>')
    dc.append('      <dc:Format>ANSI/NISO Z39.86-2005</dc:Format>')
    dc.append('      <dc:Type>text</dc:Type>')
    if meta.get("rights"):
        dc.append(f'      <dc:Rights>{escape(meta["rights"])}</dc:Rights>')

    xmeta = [
        ('dtb:totalTime', hms(total_seconds)),
        ('dtb:multimediaType', meta.get("multimedia_type", "audioFullText")),
        ('dtb:multimediaContent', 'audio,text'),
        ('dtb:narrator', 'piper (Vietnamese)'),
        ('dtb:generator', 'text_to_book pipeline'),
    ]
    x = "\n".join(f'      <meta name={quoteattr(k)} content={quoteattr(v)}/>' for k, v in xmeta)

    items = [
        '    <item id="opf" href="book.opf" media-type="text/xml"/>',
        '    <item id="ncx" href="book.ncx" media-type="application/x-dtbncx+xml"/>',
        '    <item id="dtbook" href="book.dtbook.xml" media-type="application/x-dtbook+xml"/>',
        '    <item id="smil" href="book.smil" media-type="application/smil"/>',
    ]
    for i, af in enumerate(sorted(audio_files), 1):
        items.append(f'    <item id="aud_{i:04d}" href={quoteattr("audio/" + af)} media-type="audio/mpeg"/>')
    if cover_name:
        mt = _MIME.get(Path(cover_name).suffix.lower(), "image/jpeg")
        items.append(f'    <item id="cover" href={quoteattr("images/" + cover_name)} media-type={quoteattr(mt)}/>')

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n' + OPF_DOCTYPE + "\n"
        '<package xmlns="http://openebook.org/namespaces/oeb-package/1.0/" '
        'unique-identifier="uid">\n'
        "  <metadata>\n"
        '    <dc-metadata xmlns:dc="http://purl.org/dc/elements/1.1/">\n'
        + "\n".join(dc) + "\n"
        "    </dc-metadata>\n"
        "    <x-metadata>\n" + x + "\n    </x-metadata>\n"
        "  </metadata>\n"
        "  <manifest>\n" + "\n".join(items) + "\n  </manifest>\n"
        '  <spine>\n    <itemref idref="smil"/>\n  </spine>\n'
        "</package>\n"
    )


def main() -> None:
    args = common.base_argparser(__doc__).parse_args()
    run_id = common.use_latest_run(args.run_id)
    log.info("run_id: %s", run_id)
    cfg = common.load_config()
    meta = cfg.get("metadata", {})
    audio_dir_name = cfg.get("step_06_package", {}).get("audio_dir_name", "audio")

    model = common.load_json(common.step_dir(3, create=False) / "doc_model.json")
    chapters = model["chapters"]
    if args.chapter:
        wanted = set(args.chapter.split(","))
        chapters = [c for c in chapters if c["id"] in wanted]
    if args.limit:
        chapters = chapters[: args.limit]

    s3 = common.step_dir(3, create=False) / "chapters"
    s4 = common.step_dir(4, create=False) / "chapters"
    s5 = common.step_dir(5, create=False) / "chapters"
    s0 = common.step_dir(0, create=False)
    covers = sorted(s0.glob("cover.*"))
    cover = covers[0] if covers else None

    out = common.step_dir(6)
    daisy = out / "daisy"
    for ch in chapters:
        cid = ch["id"]
        bdir = daisy / cid
        (bdir / audio_dir_name).mkdir(parents=True, exist_ok=True)

        shutil.copy2(s3 / cid / "book.dtbook.xml", bdir / "book.dtbook.xml")
        shutil.copy2(s5 / cid / "book.smil", bdir / "book.smil")
        for mp3 in (s4 / cid / "audio").glob("*.mp3"):
            shutil.copy2(mp3, bdir / audio_dir_name / mp3.name)

        cover_name = None
        if cover:
            (bdir / "images").mkdir(exist_ok=True)
            cover_name = "cover" + cover.suffix.lower()
            shutil.copy2(cover, bdir / "images" / cover_name)

        nav = common.load_json(s5 / cid / "nav.json")
        timings = common.load_json(s4 / cid / "timings.json")
        uid = f'{meta.get("isbn") or meta.get("book_slug", "book")}-{cid}'
        audio_files = [p.name for p in (bdir / audio_dir_name).glob("*.mp3")]

        (bdir / "book.ncx").write_text(build_ncx(ch, nav, meta, uid), encoding="utf-8")
        (bdir / "book.opf").write_text(
            build_opf(ch, meta, uid, audio_files, cover_name, timings.get("_total", 0.0)),
            encoding="utf-8",
        )
        log.info("  %s  %d mp3  %s  -> %s", cid, len(audio_files),
                 hms(nav["total_seconds"]), bdir)

    log.info("done: %d books -> %s", len(chapters), daisy)


if __name__ == "__main__":
    main()

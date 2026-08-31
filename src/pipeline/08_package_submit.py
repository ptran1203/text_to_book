"""Step 08 - build the submission tree (zip + SHA-256) per the README layout.

    output/step_08/
      <MSHV1_MSHV2_MSHV3>/
        <book_slug>-Chuong 1/
          <zip_basename>.zip                 (book.opf, .ncx, .dtbook.xml, .smil, audio/*.mp3, images/*)
          <zip_basename>_sha256sums.txt      one line per file inside the zip
        <book_slug>-Chuong 2/
          ...
      submission_manifest.json

Uses the mastered output from step 07 when present, else step 06.
"""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common

log = common.get_logger("step08")


def collect_members(book_dir: Path) -> list[Path]:
    return sorted(p for p in book_dir.rglob("*") if p.is_file())


def main() -> None:
    args = common.base_argparser(__doc__).parse_args()
    cfg = common.load_config()
    scfg = cfg.get("step_08_submit", {})
    meta = cfg.get("metadata", {})

    mshv = meta.get("mshv", []) or ["MSHV"]
    mshv_folder = "_".join(str(x) for x in mshv)
    slug = meta.get("book_slug", "book")
    zbase = scfg.get("zip_basename", "Ten_sach")
    per_member = bool(scfg.get("sha256_of_members", True))

    mastered = common.step_dir(7, create=False) / "mastered"
    daisy = common.step_dir(6, create=False) / "daisy"
    src_root = mastered if mastered.exists() and any(mastered.iterdir()) else daisy
    if not src_root.exists():
        sys.exit("no DAISY books found - run steps 06 (and 07) first")

    books = sorted(p for p in src_root.iterdir() if p.is_dir())
    if args.chapter:
        books = [b for b in books if b.name == args.chapter]
    if args.limit:
        books = books[: args.limit]

    out = common.step_dir(8)
    team_dir = out / mshv_folder
    manifest = dict(mshv=mshv, book=meta.get("title", ""), isbn=meta.get("isbn", ""),
                    source=str(src_root.relative_to(common.ROOT)), items=[])

    for i, book in enumerate(books, 1):
        ch_dir = team_dir / f"{slug}-Chuong {i}"
        ch_dir.mkdir(parents=True, exist_ok=True)
        zip_path = ch_dir / f"{zbase}.zip"
        members = collect_members(book)

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for m in members:
                zf.write(m, m.relative_to(book).as_posix())

        sums = ch_dir / f"{zbase}_sha256sums.txt"
        with open(sums, "w", encoding="utf-8", newline="\n") as fh:
            if per_member:
                for m in members:
                    fh.write(f"{common.sha256_file(m)}  {m.relative_to(book).as_posix()}\n")
            fh.write(f"{common.sha256_file(zip_path)}  {zip_path.name}\n")

        manifest["items"].append(dict(
            chapter_id=book.name, folder=str(ch_dir.relative_to(out)),
            zip=zip_path.name, n_files=len(members),
            zip_sha256=common.sha256_file(zip_path),
        ))
        log.info("  %s -> %s  (%d files)", book.name, ch_dir, len(members))

    common.dump_json(manifest, out / "submission_manifest.json")
    log.info("done: %d chapter zips -> %s", len(books), team_dir)


if __name__ == "__main__":
    main()

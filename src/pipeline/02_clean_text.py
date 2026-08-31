"""Step 02 - turn raw OCR text into clean paragraph text.

Per page:
  * Unicode NFC (+ ftfy mojibake repair if installed)
  * strip recurring running headers / footers and page-number-only lines
  * de-hyphenate words broken across a line end
  * join lines that are wrapped mid-paragraph; keep blank lines as para breaks
  * apply the regex replacement list from pipeline.yaml
  * optional Hunspell check -> flagged tokens into issues.csv

Outputs
    output/step_02/pages/p0001.txt      cleaned, one blank line between paragraphs
    output/step_02/full_text.txt        whole book, page markers as  <<<PAGE n>>>
    output/step_02/issues.csv           page, kind, detail
"""
from __future__ import annotations

import csv
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common

try:
    import ftfy
except ImportError:
    ftfy = None

log = common.get_logger("step02")

_PAGENUM_LINE = re.compile(r"^\s*[-–—\[(]?\s*\d{1,4}\s*[-–—\])]?\s*$")
_SENT_END = re.compile(r"[.!?…:;”’)]$")
_HYPHEN_BREAK = re.compile(r"(\w)[-‐­]\n(\w)")


def norm_line(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def load_pages() -> list[tuple[int, str]]:
    tdir = common.step_dir(1, create=False) / "txt"
    pages = []
    for f in sorted(tdir.glob("p*.txt")):
        idx = int(f.stem[1:])
        pages.append((idx, f.read_text(encoding="utf-8")))
    return pages


def detect_furniture(pages, min_ratio: float) -> set[str]:
    """Lines that recur as the first or last non-empty line across many pages."""
    edges = Counter()
    for _, txt in pages:
        lines = [ln for ln in txt.splitlines() if ln.strip()]
        if not lines:
            continue
        edges[norm_line(lines[0])] += 1
        edges[norm_line(lines[-1])] += 1
    thresh = max(3, int(min_ratio * len(pages)))
    return {k for k, v in edges.items() if v >= thresh and len(k) > 1}


def clean_page(txt: str, furniture: set[str], scfg: dict, repls) -> tuple[str, list]:
    issues = []
    if ftfy:
        txt = ftfy.fix_text(txt)
    txt = common.nfc(txt)

    if scfg.get("dehyphenate_linebreaks", True):
        txt = _HYPHEN_BREAK.sub(r"\1\2", txt)

    kept = []
    for ln in txt.splitlines():
        n = norm_line(ln)
        if not n:
            kept.append("")
            continue
        if scfg.get("strip_running_headers", True) and n in furniture:
            issues.append(("furniture", ln.strip()))
            continue
        if scfg.get("drop_pagenumber_lines", True) and _PAGENUM_LINE.match(ln):
            issues.append(("pagenumber", ln.strip()))
            continue
        kept.append(ln.strip())

    # join wrapped lines within a paragraph
    if scfg.get("join_wrapped_lines", True):
        paras, buf = [], []
        for ln in kept:
            if not ln:
                if buf:
                    paras.append(" ".join(buf))
                    buf = []
                continue
            if buf and not _SENT_END.search(buf[-1]) and ln[:1].islower():
                buf[-1] = buf[-1] + " " + ln
            else:
                buf.append(ln)
        if buf:
            paras.append(" ".join(buf))
        text = "\n\n".join(paras)
    else:
        text = "\n".join(kept)

    for pat, rep in repls:
        text = re.sub(pat, rep, text)

    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text, issues


def hunspell_flags(text: str, dic_dir: Path):
    try:
        import hunspell  # type: ignore
    except ImportError:
        return None
    hs = hunspell.HunSpell(str(dic_dir / "vi_VN.dic"), str(dic_dir / "vi_VN.aff"))
    bad = []
    for tok in set(re.findall(r"[^\W\d_]+", text, flags=re.UNICODE)):
        if len(tok) > 2 and not hs.spell(tok):
            bad.append(tok)
    return bad


def main() -> None:
    args = common.base_argparser(__doc__).parse_args()
    cfg = common.load_config()
    scfg = cfg.get("step_02_clean", {})
    repls = [(p, r) for p, r in scfg.get("replacements", [])]

    pages = load_pages()
    if args.limit:
        pages = pages[: args.limit]
    if not pages:
        sys.exit("no OCR text found - run step 01 first")

    furniture = detect_furniture(pages, float(scfg.get("running_header_min_ratio", 0.30)))
    log.info("running-furniture lines detected: %d", len(furniture))

    out = common.step_dir(2)
    (out / "pages").mkdir(exist_ok=True)

    hs_cfg = scfg.get("hunspell", {}) or {}
    hs_dir = Path(hs_cfg.get("dict_dir", "")) if hs_cfg.get("enabled") else None

    issue_rows, full = [], []
    for idx, raw in pages:
        text, issues = clean_page(raw, furniture, scfg, repls)
        (out / "pages" / f"p{idx:04d}.txt").write_text(text, encoding="utf-8")
        for kind, detail in issues:
            issue_rows.append((idx, kind, detail))
        if hs_dir and hs_dir.exists():
            bad = hunspell_flags(text, hs_dir)
            if bad:
                for w in sorted(bad)[:200]:
                    issue_rows.append((idx, "spelling", w))
        full.append(f"<<<PAGE {idx}>>>\n{text}\n")

    (out / "full_text.txt").write_text("\n".join(full), encoding="utf-8")
    with open(out / "issues.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["page", "kind", "detail"])
        w.writerows(issue_rows)

    log.info("done: %d pages -> %s  (%d issues logged)", len(pages), out, len(issue_rows))


if __name__ == "__main__":
    main()

"""Step 01 - Vietnamese OCR of the page images.

For each page image: light preprocessing (grayscale / autocontrast / Otsu /
deskew) then Tesseract with lang=vie, producing:

    output/step_01/hocr/p0001.hocr      structured OCR (used by step 03 for
                                        heading detection via glyph heights)
    output/step_01/txt/p0001.txt        plain text
    output/step_01/confidence.csv       page, mean_conf, n_words, n_low_conf
    output/step_01/lowconf.csv          page, word, conf   (conf < threshold)

Requires the Tesseract binary + the 'vie' traineddata, and pytesseract.
"""
from __future__ import annotations

import csv
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common

from PIL import Image, ImageOps

try:
    import numpy as np
except ImportError:
    np = None

import pytesseract

log = common.get_logger("step01")


def preprocess(img: Image.Image, p: dict) -> Image.Image:
    if p.get("grayscale", True):
        img = img.convert("L")
    if p.get("autocontrast", True):
        img = ImageOps.autocontrast(img)
    if np is None:
        return img
    arr = np.asarray(img).astype("float32")
    if p.get("deskew", True) and arr.ndim == 2:
        arr = _deskew(arr)
    if p.get("otsu_threshold", True) and arr.ndim == 2:
        arr = _otsu(arr)
    return Image.fromarray(arr.astype("uint8"))


def _otsu(arr):
    hist, _ = np.histogram(arr, bins=256, range=(0, 255))
    total = arr.size
    sum_all = np.dot(np.arange(256), hist)
    w_b = 0.0
    sum_b = 0.0
    best_t, best_var = 127, -1.0
    for t in range(256):
        w_b += hist[t]
        if w_b == 0:
            continue
        w_f = total - w_b
        if w_f == 0:
            break
        sum_b += t * hist[t]
        m_b = sum_b / w_b
        m_f = (sum_all - sum_b) / w_f
        var = w_b * w_f * (m_b - m_f) ** 2
        if var > best_var:
            best_var, best_t = var, t
    return np.where(arr > best_t, 255, 0)


def _deskew(arr):
    # estimate skew from the angle that maximises row-sum variance of the ink mask
    ink = (arr < arr.mean()).astype("float32")
    best_ang, best_score = 0.0, -1.0
    for ang in np.arange(-2.0, 2.05, 0.25):
        rot = _rotate(ink, ang)
        score = np.var(rot.sum(axis=1))
        if score > best_score:
            best_score, best_ang = score, ang
    if abs(best_ang) < 0.1:
        return arr
    return _rotate(arr, best_ang, fill=255.0)


def _rotate(a, angle_deg, fill=0.0):
    from math import cos, sin, radians

    h, w = a.shape
    t = radians(angle_deg)
    cy, cx = h / 2.0, w / 2.0
    ys, xs = np.indices((h, w))
    xr = cos(t) * (xs - cx) - sin(t) * (ys - cy) + cx
    yr = sin(t) * (xs - cx) + cos(t) * (ys - cy) + cy
    x0 = np.clip(np.round(xr).astype(int), 0, w - 1)
    y0 = np.clip(np.round(yr).astype(int), 0, h - 1)
    out = np.full_like(a, fill)
    valid = (xr >= 0) & (xr < w) & (yr >= 0) & (yr < h)
    out[valid] = a[y0[valid], x0[valid]]
    return out


def main() -> None:
    args = common.base_argparser(__doc__).parse_args()
    cfg = common.load_config()
    scfg = cfg.get("step_01_ocr", {})
    pytesseract.pytesseract.tesseract_cmd = common.which_or_config(
        scfg.get("tesseract"), "tesseract"
    )
    lang = scfg.get("lang", "vie")
    tcfg = f"--oem {scfg.get('oem', 1)} --psm {scfg.get('psm', 6)}"
    pp = scfg.get("preprocess", {})
    thr = int(scfg.get("min_word_confidence", 60))

    manifest = common.load_json(common.step_dir(0, create=False) / "manifest.json")
    if args.limit:
        manifest = manifest[: args.limit]

    out = common.step_dir(1)
    (out / "hocr").mkdir(exist_ok=True)
    (out / "txt").mkdir(exist_ok=True)

    conf_rows, low_rows = [], []
    for e in manifest:
        idx = e["index"]
        img = Image.open(common.step_dir(0, create=False) / e["file"])
        img = preprocess(img, pp)

        hocr = pytesseract.image_to_pdf_or_hocr(
            img, lang=lang, extension="hocr", config=tcfg
        )
        (out / "hocr" / f"p{idx:04d}.hocr").write_bytes(hocr)

        text = common.nfc(pytesseract.image_to_string(img, lang=lang, config=tcfg))
        (out / "txt" / f"p{idx:04d}.txt").write_text(text, encoding="utf-8")

        data = pytesseract.image_to_data(
            img, lang=lang, config=tcfg, output_type=pytesseract.Output.DICT
        )
        confs = [
            (w, int(float(c)))
            for w, c in zip(data["text"], data["conf"])
            if w.strip() and c not in ("-1", -1)
        ]
        mean_c = round(sum(c for _, c in confs) / len(confs), 1) if confs else 0.0
        n_low = sum(1 for _, c in confs if c < thr)
        conf_rows.append((idx, mean_c, len(confs), n_low))
        low_rows.extend((idx, w, c) for w, c in confs if c < thr)

        if idx % 10 == 0 or e is manifest[-1]:
            log.info("  ocr %d/%d  (last mean conf %.1f)", idx, len(manifest), mean_c)

    with open(out / "confidence.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["page", "mean_conf", "n_words", "n_low_conf"])
        w.writerows(conf_rows)
    with open(out / "lowconf.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["page", "word", "conf"])
        w.writerows(low_rows)

    overall = round(sum(r[1] for r in conf_rows) / len(conf_rows), 1) if conf_rows else 0
    log.info("done: %d pages, overall mean confidence %.1f -> %s",
             len(conf_rows), overall, out)


if __name__ == "__main__":
    main()

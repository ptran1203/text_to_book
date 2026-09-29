"""Step 01 - line detection (Tesseract) + Vietnamese recognition (VietOCR).

Tesseract is used ONLY to find where the text lines are (image_to_data gives
line-level bounding boxes and glyph heights - the latter feeds step 03's
heading heuristic). Its own character recognition is discarded: each line crop
is instead read by VietOCR (pbcquoc/vietocr), which is far more accurate on
Vietnamese diacritics than Tesseract's 'vie' model - confirmed ~0.90+ line
confidence and near-perfect transcription on real scanned body pages.

Outputs
    output/step_01/lines/p0001.json   [{id, bbox:[x0,y0,x1,y1], height, text, conf, para}]
    output/step_01/txt/p0001.txt      plain text (blank line between Tesseract paragraphs)
    output/step_01/confidence.csv     page, mean_conf, n_lines, n_low_conf
    output/step_01/lowconf.csv        page, line_id, conf, text
"""
from __future__ import annotations

import csv
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


# --------------------------------------------------------------- preprocess
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
    if p.get("otsu_threshold", False) and arr.ndim == 2:
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
    # Find the angle on a small downsample - cheap - then rotate the full-res
    # array only once. Searching all candidate angles at full resolution (the
    # original approach) took >80s/page on a real 3626x5400 scan; this takes
    # a couple of seconds.
    h, w = arr.shape
    scale = max(1, round(max(h, w) / 600))
    small = (arr[::scale, ::scale] < arr.mean()).astype("float32")
    best_ang, best_score = 0.0, -1.0
    for ang in np.arange(-2.0, 2.05, 0.25):
        rot = _rotate(small, ang)
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


# --------------------------------------------------------------- line detect
def detect_lines(img: Image.Image, tcfg: str, lang: str) -> list[dict]:
    """Tesseract word boxes grouped into lines, in natural reading order."""
    data = pytesseract.image_to_data(
        img, lang=lang, config=tcfg, output_type=pytesseract.Output.DICT
    )
    lines: dict[tuple, dict] = {}
    order: list[tuple] = []
    for i in range(len(data["text"])):
        if not data["text"][i].strip():
            continue
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
        if key not in lines:
            lines[key] = dict(para=(data["block_num"][i], data["par_num"][i]),
                               bbox=[x, y, x + w, y + h])
            order.append(key)
        else:
            b = lines[key]["bbox"]
            b[0], b[1] = min(b[0], x), min(b[1], y)
            b[2], b[3] = max(b[2], x + w), max(b[3], y + h)
    return [lines[k] for k in order]


def build_predictor(vcfg: dict):
    from vietocr.tool.config import Cfg
    from vietocr.tool.predictor import Predictor

    cfg = Cfg.load_config_from_name(vcfg.get("config_name", "vgg_transformer"))
    cfg["device"] = vcfg.get("device", "cpu")
    if vcfg.get("weights"):
        cfg["weights"] = vcfg["weights"]
    return Predictor(cfg)


def main() -> None:
    args = common.base_argparser(__doc__).parse_args()
    run_id = common.use_latest_run(args.run_id)
    cfg = common.load_config()
    scfg = cfg.get("step_01_ocr", {})
    pytesseract.pytesseract.tesseract_cmd = common.which_or_config(
        scfg.get("tesseract"), "tesseract"
    )
    lang = scfg.get("lang", "vie")
    tcfg = f"--oem {scfg.get('oem', 1)} --psm {scfg.get('psm', 6)}"
    if scfg.get("tessdata_dir"):
        # no quotes: pytesseract's config splitter doesn't strip them on Windows,
        # so a quoted path is passed through literally (path must have no spaces).
        tcfg += f' --tessdata-dir {scfg["tessdata_dir"]}'
    pp = scfg.get("preprocess", {})
    pad_ratio = float(scfg.get("line_padding_ratio", 0.25))
    thr = float(scfg.get("min_line_confidence", 0.80))

    log.info("run_id: %s", run_id)
    log.info("loading VietOCR predictor (%s, %s) ...",
             scfg.get("vietocr", {}).get("config_name", "vgg_transformer"),
             scfg.get("vietocr", {}).get("device", "cpu"))
    predictor = build_predictor(scfg.get("vietocr", {}))

    manifest = common.load_json(common.step_dir(0, create=False) / "manifest.json")
    if args.limit:
        manifest = manifest[: args.limit]

    out = common.step_dir(1)
    (out / "lines").mkdir(exist_ok=True)
    (out / "txt").mkdir(exist_ok=True)

    prog = common.Progress(len(manifest), log, "page", out / "timing.csv")
    conf_rows, low_rows = [], []
    for e in manifest:
        idx = e["index"]
        img = Image.open(common.step_dir(0, create=False) / e["file"])
        img = preprocess(img, pp)
        img_rgb = img.convert("RGB")
        w_img, h_img = img_rgb.size

        raw_lines = detect_lines(img, tcfg, lang)
        crops, keep = [], []
        for ln in raw_lines:
            x0, y0, x1, y1 = ln["bbox"]
            if x1 - x0 < 5 or y1 - y0 < 5:
                continue
            pad = int((y1 - y0) * pad_ratio)
            box = (max(0, x0 - 8), max(0, y0 - pad), min(w_img, x1 + 8), min(h_img, y1 + pad))
            crops.append(img_rgb.crop(box))
            keep.append(ln)

        texts, probs = ([], []) if not crops else predictor.predict_batch(crops, return_prob=True)

        records, paras, cur_para, cur_key = [], [], [], None
        for j, (ln, text, prob) in enumerate(zip(keep, texts, probs), 1):
            text = common.nfc(text.strip())
            if not text:
                continue
            lid = f"p{idx:04d}_l{j:03d}"
            records.append(dict(id=lid, bbox=ln["bbox"],
                                 height=ln["bbox"][3] - ln["bbox"][1],
                                 text=text, conf=round(float(prob), 4)))
            if ln["para"] != cur_key:
                if cur_para:
                    paras.append(" ".join(cur_para))
                cur_para, cur_key = [], ln["para"]
            cur_para.append(text)
            if prob < thr:
                low_rows.append((idx, lid, round(float(prob), 4), text))
        if cur_para:
            paras.append(" ".join(cur_para))

        common.dump_json(records, out / "lines" / f"p{idx:04d}.json")
        (out / "txt" / f"p{idx:04d}.txt").write_text("\n\n".join(paras), encoding="utf-8")

        mean_c = round(sum(r["conf"] for r in records) / len(records), 3) if records else 0.0
        n_low = sum(1 for r in records if r["conf"] < thr)
        conf_rows.append((idx, mean_c, len(records), n_low))
        prog.tick(note=f"page {idx}, {len(records)} lines, conf {mean_c:.2f}")

    prog.close()
    with open(out / "confidence.csv", "w", newline="", encoding="utf-8") as fh:
        wtr = csv.writer(fh)
        wtr.writerow(["page", "mean_conf", "n_lines", "n_low_conf"])
        wtr.writerows(conf_rows)
    with open(out / "lowconf.csv", "w", newline="", encoding="utf-8") as fh:
        wtr = csv.writer(fh)
        wtr.writerow(["page", "line_id", "conf", "text"])
        wtr.writerows(low_rows)

    overall = round(sum(r[1] for r in conf_rows) / len(conf_rows), 3) if conf_rows else 0
    log.info("done: %d pages, overall mean line confidence %.3f -> %s",
             len(conf_rows), overall, out)


if __name__ == "__main__":
    main()

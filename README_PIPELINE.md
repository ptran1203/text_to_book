# text_to_book — DAISY 3 pipeline

Converts a scanned Vietnamese PDF (`data/book.pdf`) into one **DAISY 3**
talking book **per chapter** (DTBook + SMIL + MP3 + NCX + OPF), then zips each
with SHA-256 sums in the submission layout from the course README.

```
data/book.pdf
   │  00  extract      PDF pages ─► PNG                     output/step_00/
   │  01  ocr          Tesseract (vie) ─► hOCR + text       output/step_01/
   │  02  clean        de-hyphenate, join lines, strip      output/step_02/
   │                   running heads, NFC, regex fixes
   │  03  structure    headings + pages ─► DTBook per ch.    output/step_03/
   │        └── MANUAL: review config/structure.yaml
   │  04  tts          piper ─► one MP3 per sentence         output/step_04/
   │  05  smil         DTBook id ⇄ MP3 clip                  output/step_05/
   │  06  package      + NCX + OPF, assemble book folder     output/step_06/
   │  07  validate     internal checks + DAISY Pipeline 2    output/step_07/
   │  08  submit       zip + sha256sums, MSHV tree           output/step_08/
```

## 1. Install

```bash
pip install -r requirements.txt
```

External tools (not pip) — put paths in `config/pipeline.yaml`:

| Tool | Why | Notes |
|------|-----|-------|
| Tesseract OCR + `vie.traineddata` | step 01 | UB-Mannheim build on Windows |
| piper + a Vietnamese voice `.onnx` | step 04 | e.g. `vi_VN-vais1000-medium` |
| ffmpeg | step 04 | WAV → MP3 |
| DAISY Pipeline 2 (Java 11+) | step 07 | `dp2` on PATH; optional but authoritative |

## 2. Configure

- `config/metadata.yaml` — title, creators, **ISBN** (shared by all chapters),
  publisher, `mshv` (student ids → submission folder), `book_slug`.
- `config/pipeline.yaml` — tool paths and per-step knobs.

## 3. Run

```bash
# quick smoke test on the first 3 pages / chapters
python run_all.py --limit 3

# full run — stops after 03 --detect the first time
python run_all.py
#   ... edit config/structure.yaml (chapter titles + start_page = image index) ...
python run_all.py --from 3
```

Each step also runs standalone, e.g. `python src/pipeline/01_ocr.py --limit 10`.

## 4. The manual checkpoint (step 03)

`03_structure.py --detect` writes `config/structure.yaml` from a heading
heuristic (glyph height, ALL-CAPS, the `heading_regex`) plus
`output/step_03/review.md`. **Check every chapter**:

- `start_page` is the **image index** (1-based page in the PDF), not the printed
  number. `page_offset` maps image index → printed number.
- Merge false positives, add missed headings, fix titles.
- Set `front_matter` / `back_matter` page ranges (excluded from chapters).

Then `python run_all.py --from 3` builds the DTBook files.

## 5. Output

`output/step_08/<MSHV1_MSHV2_MSHV3>/<slug>-Chuong N/`
  - `Ten_sach.zip` — the DAISY 3 book
  - `Ten_sach_sha256sums.txt` — `sha256  path` per file + the zip itself

Validate independently in **Thorium Reader** / **EasyReader** before submitting
(README step 5: audio + spelling QA). Deadline: **2026-09-30**.

## Notes / limits

- piper is not a DAISY Pipeline 2 TTS engine, so steps 04–06 build audio+SMIL in
  Python; DP2 in step 07 is the validator/master. To let DP2 do TTS instead,
  switch to a SAPI/espeak voice and use `dtbook-to-daisy3`.
- Clip timing comes from the WAV frame count (sample-accurate); enable
  `step_07_validate.run_mastering` to have DP2 renormalise SMIL timing/metadata.
- Sentence splitting is regex-based; tune in `03_structure.py` (`_SENT`).
- Copyright: this is a modern translation — confirm your course has cleared it.

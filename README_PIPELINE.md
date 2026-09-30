# text_to_book — DAISY 3 pipeline

Converts a scanned Vietnamese PDF (`data/book.pdf`) into one **DAISY 3**
talking book **per chapter** (DTBook + SMIL + MP3 + NCX + OPF), then zips each
with SHA-256 sums in the submission layout from the course README.

```
data/book.pdf                                    (all output under output/<run_id>/)
   │  00  extract      PDF pages ─► PNG                     step_00/
   │  01  ocr          Tesseract detects lines ─► VietOCR    step_01/
   │                   reads them (far more accurate on
   │                   Vietnamese diacritics than Tesseract's
   │                   own 'vie' recognizer - confirmed ~0.90+
   │                   line confidence on real scanned pages)
   │  02  clean        de-hyphenate, join lines, strip      step_02/
   │                   running heads, NFC, regex fixes
   │  03  structure    headings + pages ─► DTBook per ch.    step_03/
   │        └── MANUAL: review config/structure.yaml
   │  04  tts          piper ─► one MP3 per sentence         step_04/
   │  05  smil         DTBook id ⇄ MP3 clip                  step_05/
   │  06  package      + NCX + OPF, assemble book folder     step_06/
   │  07  validate     internal checks + DAISY Pipeline 2    step_07/
   │  08  submit       zip + sha256sums, MSHV tree           step_08/
```

## 0. Get the source PDF

`data/book.pdf` is **not in the repo** (gitignored — copyrighted scanned book).
On a fresh clone, put your own scanned book at that exact path first — nothing
else in this pipeline works without it. It must be a real scan (no text
layer); see README_PIPELINE.md's own history for how that was confirmed
(PyMuPDF `get_text()` returns nothing, no `/Font` resource, no `Tj`/`TJ` in
the content stream).

## 1. Install

```bash
pip install -r requirements.txt
pip install vietocr
pip install torch --index-url https://download.pytorch.org/whl/cpu   # or the CUDA wheel from pytorch.org if you have a GPU
```

External tools (not pip) — put paths in `config/pipeline.yaml`. On Windows,
`scripts\install_windows.ps1` fetches/installs most of these automatically
(Tesseract, ffmpeg, piper + voice, DAISY Pipeline 2 installer); run
`scripts\verify_install.ps1` afterward (in a **new** terminal) to confirm and
get the exact paths to paste into `pipeline.yaml`.

| Tool | Why | Notes |
|------|-----|-------|
| Tesseract OCR + `vie.traineddata` | step 01 | line/word **detection** only, not recognition |
| torch + `vietocr` | step 01 | Vietnamese **recognition**; GPU (`cuda:0`) if available, else `cpu` in config |
| piper + a Vietnamese voice `.onnx` | step 04 | e.g. `vi_VN-vais1000-medium` (best quality tier piper has for Vietnamese) |
| ffmpeg | step 04 | WAV → MP3 |
| DAISY Pipeline 2 (Java 11+) | step 07 | `dp2` on PATH; optional but authoritative - installer is GUI-only, can't be scripted |

## 2. Configure

- `config/metadata.yaml` — title, creators, **ISBN** (shared by all chapters),
  publisher, `mshv` (student ids → submission folder), `book_slug`.
- `config/pipeline.yaml` — tool paths and per-step knobs.
- `config/tts_pronunciations.yaml` — optional TTS-only pronunciation overrides
  (e.g. English names/terms a Vietnamese-only voice mispronounces). Only
  affects what's spoken, never the displayed/DTBook text. Grow this file as
  you listen and find more; see §7 below for how to apply a correction
  cheaply to already-built audio.

## 3. Runs are timestamped

Every pipeline run writes to its own `output/<run_id>/` folder (`run_id` =
`YYYYMMDD_HHMMSS`), so rerunning never clobbers a previous run. `00_extract_pages.py`
always starts a **new** run; every other step defaults to continuing the most
recently started one (tracked in `output/.current_run`), so the normal
"00, then 01, then 02, ..." workflow needs no extra flags. Pass `--run-id
20260912_181123` to any step (or to `run_all.py`) to target a specific past
run instead - e.g. to resume one that stopped partway through.

## 4. Run

```bash
# quick smoke test on the first 3 pages / chapters
python run_all.py --limit 3

# full run — stops after 03 --detect the first time
python run_all.py
#   ... edit config/structure.yaml (chapter titles + start_page = image index) ...
python run_all.py --from 3
```

Each step also runs standalone, e.g. `python src/pipeline/01_ocr.py --limit 10`.

## 5. The manual checkpoint (step 03)

`03_structure.py --detect` writes `config/structure.yaml` from a heading
heuristic (glyph height, ALL-CAPS, the `heading_regex`) plus
`output/<run_id>/step_03/review.md`. **Check every chapter**:

- `start_page` is the **image index** (1-based page in the PDF), not the printed
  number. `page_offset` maps image index → printed number.
- Merge false positives, add missed headings, fix titles.
- Set `front_matter` / `back_matter` page ranges (excluded from chapters).

Then `python run_all.py --from 3` builds the DTBook files.

## 6. Output

`output/<run_id>/step_08/<mshv>/<slug>-Chuong N/`
  - `<slug>.zip` — the DAISY 3 book (basename follows `metadata.yaml`'s `book_slug`)
  - `<slug>_sha256sums.txt` — `sha256  path` per file + the zip itself

Chapters are routinely rebuilt/fixed across several different runs, so no
single `output/<run_id>/step_08/` has every chapter. Two cross-run reports
gather the real picture (scan every run, not just the latest):

```bash
python src/pipeline/09_measure_duration.py       # real narrated seconds per member vs the 1h/person requirement
python src/pipeline/10_consolidate_submission.py # copies each chapter's LATEST build into one output/SUBMISSION/<mshv>/ tree
```

`output/SUBMISSION/<mshv>/` is the actual thing to submit - not any single run's `step_08`.

Validate independently in **Thorium Reader** / **EasyReader** before submitting
(README step 5: audio + spelling QA). Deadline: **2026-09-30**.

## 7. Fixing a mistake after audio is already built

Real gotchas hit while producing this book - read before touching a chapter
that's already been synthesized:

- **A run holding several chapters must be rebuilt with all of them listed
  together**: `03_structure.py`, `04_tts.py`, etc. accept a comma-separated
  `--chapter ch02,ch03`. Rebuilding one chapter at a time in separate calls
  **overwrites** that run's shared `doc_model.json` down to just the last
  chapter called - the earlier chapter's fix silently never gets synthesized,
  even though every log line says "done".
- **Don't trust the resume counter.** `04_tts.py` skips re-synthesizing a
  clip whose id already has an mp3 on disk - fast, but if a text edit
  happens to leave a sentence's id unchanged (e.g. it's still paragraph 1,
  sentence 1, after restructuring the page), resume keeps the **old, wrong**
  audio under that id without any sign of it in the "N resumed" count. After
  any content fix, verify by comparing the mp3's file `mtime` against the
  edited `step_02` `.txt`'s mtime for every sentence on the changed page -
  don't assume resumed == correct.
- **Changing a page's paragraph count reshuffles every sentence id after
  it** (ids are assigned sequentially per chapter, not per page), forcing a
  full re-synthesis of the rest of the chapter. If you're only fixing
  garbled words/typos, keep the exact same number of blank-line-separated
  paragraphs the page had before your edit - cheap, targeted resynthesis
  instead of redoing the whole chapter.

## Notes / limits

- Step 01 is two-stage: Tesseract only detects line boxes (`--tessdata-dir` is
  for that detection pass, language barely matters); VietOCR does the actual
  reading. `min_line_confidence` in `pipeline.yaml` is on VietOCR's 0-1 scale,
  not Tesseract's old 0-100 word confidence.
- piper is not a DAISY Pipeline 2 TTS engine, so steps 04–06 build audio+SMIL in
  Python; DP2 in step 07 is the validator/master. To let DP2 do TTS instead,
  switch to a SAPI/espeak voice and use `dtbook-to-daisy3`.
- Clip timing comes from the WAV frame count (sample-accurate); enable
  `step_07_validate.run_mastering` to have DP2 renormalise SMIL timing/metadata.
- Sentence splitting is regex-based; tune in `03_structure.py` (`_SENT`).
- Copyright: this is a modern translation — confirm your course has cleared it.

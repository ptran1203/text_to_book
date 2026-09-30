# Commands

Quick reference. Details/rationale: [README_PIPELINE.md](README_PIPELINE.md).

## Setup (once)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install_windows.ps1
# double-click the downloaded C:\tools\daisy-pipeline-setup-1.12.0.exe and click through setup (GUI, can't be scripted)
pip install vietocr
pip install torch --index-url https://download.pytorch.org/whl/cpu   # or the CUDA wheel from pytorch.org if you have an NVIDIA GPU
pip install -r requirements.txt
```

Check everything is actually in place (open a NEW terminal first, so PATH updates apply):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\verify_install.ps1
```

## Configure (once per book)

- `config/metadata.yaml` — title, creators, **ISBN**, publisher, `mshv`, `book_slug`.
- `config/pipeline.yaml` — tool paths (verify_install.ps1 tells you what to paste in for `dp2`).

## Run

```powershell
# 1. quick smoke test - first 3 pages/chapters only
python run_all.py --limit 3

# jump straight past front matter into a page range (skips OCR-ing pages you don't need)
python run_all.py --only 0 --page-start 15 --page-end 40
python run_all.py --from 1 --to 3          # OCR/clean/detect on whatever step 00 just extracted

# 2. full run - stops after step 03 writes config/structure.yaml for you to review
python run_all.py

# 3. after editing config/structure.yaml (chapter titles + start_page = image index):
python run_all.py --from 3

# 4. build the full chapter's audio+book (steps 04-08), continuing that same run
python run_all.py --from 4 --run-id 20260919_194856
```

Each step also runs alone, e.g.:

```powershell
python src\pipeline\00_extract_pages.py --limit 10
python src\pipeline\00_extract_pages.py --start 15 --end 40   # jump straight into a chapter, skip front matter
python src\pipeline\01_ocr.py --limit 10                       # OCRs whatever step 00 extracted for this run
python src\pipeline\03_structure.py --detect      # (re)seed config/structure.yaml
python src\pipeline\07_validate.py --chapter ch01
```

## Runs are timestamped

Every run writes to its own `output/<run_id>/`. Step 00 always starts a **new**
run; every other step defaults to the **latest** run. Target a specific past
run explicitly:

```powershell
python run_all.py --from 3 --run-id 20260912_181123
python src\pipeline\04_tts.py --run-id 20260912_181123 --chapter ch02
```

## Output

Chapters are usually built across several different runs (fixes, extended
ranges, rebuilds), so no single `output/<run_id>/step_08/` has everything -
run this to gather each chapter's latest build into one real submission tree:

```powershell
python src\pipeline\10_consolidate_submission.py
```

```
output/SUBMISSION/<mshv_folder>/<book_slug>-Chuong N/
    <book_slug>.zip
    <book_slug>_sha256sums.txt
```

## Per-member speech-time requirement (1h each)

Set `assigned_to: MSHV1` on each chapter in `config/structure.yaml`, then:

```powershell
python src\pipeline\09_measure_duration.py
```

Scans every run's TTS output (not just the latest), sums duration per member,
and checks it against `requirements.min_seconds_per_member` in
`config/pipeline.yaml` (default 3600s = 1h). Writes `output/duration_report.md`
+ `.json`; exits non-zero if anyone is short.

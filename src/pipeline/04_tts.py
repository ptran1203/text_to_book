"""Step 04 - synthesize one MP3 per sentence with piper (offline Vietnamese TTS).

For every <sent> / <h1> id in doc_model.json we render a WAV with piper, measure
its exact duration from the WAV header (sample-accurate), then transcode to MP3
with ffmpeg.

Outputs
    output/step_04/chapters/<id>/audio/<sent-id>.mp3
    output/step_04/chapters/<id>/timings.json   { id: {file, dur} , _total: seconds }

Config: step_04_tts.{piper, model, ffmpeg, mp3_qscale, length_scale}
"""
from __future__ import annotations

import sys
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common

log = common.get_logger("step04")


def load_pronunciations() -> list[tuple[str, str]]:
    """(original, spoken) pairs from config/tts_pronunciations.yaml, longest
    original-phrase first so multi-word names match before their substrings
    (e.g. "Pete Carroll" before a lone "Carroll" would ever be added)."""
    data = common.load_yaml(common.CONFIG_DIR / "tts_pronunciations.yaml") or {}
    items = list((data.get("replacements") or {}).items())
    return sorted(items, key=lambda kv: -len(kv[0]))


def apply_pronunciations(text: str, pron: list[tuple[str, str]]) -> str:
    """Substitute English names/terms with a Vietnamese-spelled approximation
    for TTS ONLY - the caller's copy of the DTBook text is untouched."""
    for orig, spoken in pron:
        if orig in text:
            text = text.replace(orig, spoken)
    return text


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / float(w.getframerate() or 1)


def piper_say(piper: str, model: str, text: str, wav_out: Path, length_scale: float) -> None:
    wav_out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [piper, "--model", model, "--output_file", str(wav_out),
           "--length_scale", str(length_scale)]
    common.run(cmd, stdin_text=text.replace("\n", " ").strip() + "\n", capture=True)


def transcode(ffmpeg: str, wav: Path, mp3: Path, qscale: int) -> None:
    common.run(
        [ffmpeg, "-y", "-loglevel", "error", "-i", str(wav),
         "-codec:a", "libmp3lame", "-qscale:a", str(qscale), str(mp3)],
        capture=True,
    )


def iter_units(chapter: dict):
    """Yield (id, text) for every audio-bearing leaf, in reading order.

    Page numbers get spoken too, so the book is a clean audioFullText title
    (every SMIL <par> carries audio)."""
    yield f'{chapter["id"]}_h', chapter["title"]
    for b in chapter["blocks"]:
        if b["type"] == "pagenum":
            yield b["id"], f'Trang {b["printed"]}'
        elif b["type"] == "p":
            for s in b["sents"]:
                if s["text"].strip():
                    yield s["id"], s["text"]


def main() -> None:
    args = common.base_argparser(__doc__).parse_args()
    run_id = common.use_latest_run(args.run_id)
    log.info("run_id: %s", run_id)
    cfg = common.load_config()
    scfg = cfg.get("step_04_tts", {})
    piper = common.which_or_config(scfg.get("piper"), "piper")
    model = scfg.get("model", "")
    ffmpeg = common.which_or_config(scfg.get("ffmpeg"), "ffmpeg")
    qscale = int(scfg.get("mp3_qscale", 4))
    length_scale = float(scfg.get("length_scale", 1.0))
    if not model or not Path(model).exists():
        sys.exit(f"piper model not found: {model!r}  (set step_04_tts.model in pipeline.yaml)")
    pron = load_pronunciations()
    log.info("loaded %d TTS pronunciation substitutions", len(pron))

    model_doc = common.load_json(common.step_dir(3, create=False) / "doc_model.json")
    chapters = model_doc["chapters"]
    if args.chapter:
        wanted = set(args.chapter.split(","))
        chapters = [c for c in chapters if c["id"] in wanted]
    if args.limit:
        chapters = chapters[: args.limit]

    out = common.step_dir(4)
    for ch in chapters:
        cdir = out / "chapters" / ch["id"]
        adir = cdir / "audio"
        adir.mkdir(parents=True, exist_ok=True)
        tmp_wav = cdir / "_tmp.wav"
        tpath = cdir / "timings.json"

        # Resume support: a clip already on disk (mp3 file + a recorded duration
        # from a prior, possibly-interrupted run of this same chapter) is reused
        # rather than resynthesized. timings.json is rewritten after every clip
        # (not just at the end) specifically so a stopped run doesn't lose this.
        timings = {k: v for k, v in (common.load_json(tpath) if tpath.exists() else {}).items()
                   if k != "_total"}
        total = sum(v["dur"] for v in timings.values())
        n_resumed = 0

        units = list(iter_units(ch))
        prog = common.Progress(len(units), log, "clip", cdir / "timing.csv", log_every=10)
        for uid, text in units:
            mp3 = adir / f"{uid}.mp3"
            if uid in timings and mp3.exists():
                n_resumed += 1
                prog.tick(note=f"{ch['id']}, cached, {total:.1f}s audio so far")
                continue
            piper_say(piper, model, apply_pronunciations(text, pron), tmp_wav, length_scale)
            dur = round(wav_duration(tmp_wav), 3)
            transcode(ffmpeg, tmp_wav, mp3, qscale)
            timings[uid] = dict(file=f"audio/{uid}.mp3", dur=dur)
            total += dur
            common.dump_json(dict(timings, _total=round(total, 3)), tpath)
            prog.tick(note=f"{ch['id']}, {total:.1f}s audio so far")
        prog.close()
        tmp_wav.unlink(missing_ok=True)

        common.dump_json(dict(timings, _total=round(total, 3)), tpath)
        log.info("%s done: %d clips (%d resumed from a prior run), %.1fs total audio",
                 ch["id"], len(units), n_resumed, total)

    log.info("done -> %s", out)


if __name__ == "__main__":
    main()

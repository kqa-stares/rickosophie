"""Join the paragraphs made by omni_long.py into one voice track, then measure its pace like the reference channel.

  cd tools && PYTHONUTF8=1 C:/Users/wqach/chatterbox/.venv/Scripts/python.exe join_parts.py ../tests/telephone [pause=0.45] [stretch=0.32]

Join: each part keeps its own natural start and tail (never digital silence glued to speech); the gap between two
parts is brought to `pause` seconds with noise at the level of the track's own quiet moments.
stretch (optional, 0 = off): every sentence-end gap shorter than this is lengthened to it, by inserting the same
quiet noise at the quietest point of the gap. This gives the voice room to breathe without cutting any sound.
Writes <folder>/voix.wav (24 kHz) + pace.json (words per second, pauses) to compare with refs-chaines/analysis/*.json.
"""
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

SR = 24000


def rms_db(x):
    return 20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-9)


def quiet_noise(n, level_db, rng):
    """n samples of soft noise at level_db (so a pause never sounds like the track was switched off)."""
    return (rng.standard_normal(n) * 10 ** (level_db / 20)).astype(np.float32)


def edges(x, top_db=38, frame=int(0.01 * SR)):
    """First and last sample of speech (10 ms frames louder than peak frame - top_db)."""
    e = np.array([np.sqrt(np.mean(x[i:i + frame] ** 2)) for i in range(0, len(x) - frame, frame)])
    loud = np.where(20 * np.log10(e + 1e-9) > 20 * np.log10(e.max() + 1e-9) - top_db)[0]
    return loud[0] * frame, min(len(x), (loud[-1] + 1) * frame)


def floor_db(x, frame=int(0.02 * SR)):
    e = np.array([rms_db(x[i:i + frame]) for i in range(0, len(x) - frame, frame)])
    return float(np.clip(np.percentile(e, 3), -80, -50))


def fade(x, n, start=True):
    x = x.copy()
    n = min(n, len(x))
    ramp = np.linspace(0, 1, n, dtype=np.float32)
    if start:
        x[:n] *= ramp
    else:
        x[-n:] *= ramp[::-1]
    return x


def word_times(path):
    from faster_whisper import WhisperModel
    model = WhisperModel("small", device="cpu", compute_type="int8")
    segs, _ = model.transcribe(str(path), language="fr", word_timestamps=True, vad_filter=True,
                               condition_on_previous_text=False)
    return [(w.start, w.end, w.word.strip()) for s in segs for w in s.words]


def pace(words, total):
    gaps = [(b[0] - a[1], a[2], b[2], a[1]) for a, b in zip(words, words[1:])]
    pauses = [g for g in gaps if g[0] >= 0.25]
    ends = [g[0] for g in gaps if g[1][-1:] in ".!?…"]
    return {"seconds": round(total, 1), "words": len(words), "words_per_s_overall": round(len(words) / total, 2),
            "first_word_at_s": round(words[0][0], 2), "pauses_ge_0.25s": len(pauses),
            "pause_total_s": round(sum(g[0] for g in pauses), 1),
            "pause_median_s": round(float(np.median([g[0] for g in pauses])), 2) if pauses else 0,
            "pause_max_s": round(max(g[0] for g in pauses), 2) if pauses else 0,
            "sentence_ends": len(ends), "sentence_end_gap_median_s": round(float(np.median(ends)), 2) if ends else None,
            "sentence_end_gaps_under_0.2s": sum(1 for g in ends if g < 0.2)}


def main(folder, *opts):
    folder = Path(folder).resolve()
    pause = next((float(o.split("=")[1]) for o in opts if o.startswith("pause=")), 0.45)
    stretch = next((float(o.split("=")[1]) for o in opts if o.startswith("stretch=")), 0.0)
    rng = np.random.default_rng(0)
    parts = []
    for p in sorted(folder.glob("part_*.wav"), key=lambda p: int(p.stem.split("_")[1])):
        x, sr = sf.read(p, dtype="float32")
        assert sr == SR, sr
        parts.append(x.mean(axis=1) if x.ndim == 2 else x)
    level = min(floor_db(x) for x in parts)
    out = []
    for k, x in enumerate(parts):
        a, b = edges(x)
        head = max(0, a - int(0.03 * SR)) if k else max(0, a - int(0.01 * SR))  # the video starts on the first word
        tail = min(len(x), b + int(0.12 * SR))
        seg = fade(fade(x[head:tail], int(0.008 * SR)), int(0.03 * SR), start=False)
        if k:
            have = (a - head) / SR + 0.12
            out.append(quiet_noise(max(0, int((pause - have) * SR)), level, rng))
        out.append(seg)
    voice = np.concatenate(out)
    sf.write(folder / "voix.wav", voice, SR)
    words = word_times(folder / "voix.wav")
    stats = {"before_stretch": pace(words, len(voice) / SR)} if stretch else {}

    if stretch:
        frame = int(0.01 * SR)
        pieces, cursor, added = [], 0, 0
        for a, b in zip(words, words[1:]):
            gap = b[0] - a[1]
            if a[2][-1:] not in ".!?…" or gap >= stretch:
                continue
            lo, hi = int(a[1] * SR), max(int(b[0] * SR), int(a[1] * SR) + frame)
            lo, hi = max(cursor, lo - int(0.04 * SR)), min(len(voice) - frame, hi + int(0.04 * SR))
            if hi - lo < frame:
                continue
            e = [np.mean(voice[i:i + frame] ** 2) for i in range(lo, hi, frame)]
            cut = lo + int(np.argmin(e)) * frame + frame // 2          # quietest 10 ms around the sentence end
            if rms_db(voice[cut - frame // 2:cut + frame // 2]) > -38:  # no real silence there: leave it alone
                continue
            n = int((stretch - max(gap, 0)) * SR)
            pieces += [fade(voice[cursor:cut], int(0.006 * SR), start=False), quiet_noise(n, level, rng)]
            cursor, added = cut, added + 1
            voice[cut:cut + int(0.006 * SR)] *= np.linspace(0, 1, int(0.006 * SR), dtype=np.float32)
        pieces.append(voice[cursor:])
        voice = np.concatenate(pieces)
        sf.write(folder / "voix.wav", voice, SR)
        words = word_times(folder / "voix.wav")
        stats["pauses_lengthened"] = added
    stats.update(pace(words, len(voice) / SR))
    (folder / "pace.json").write_text(json.dumps(stats, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False, indent=1))
    print("heard:", " ".join(w[2] for w in words))


if __name__ == "__main__":
    main(*sys.argv[1:])

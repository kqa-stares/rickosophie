"""Check one generated take against the text it should say, and cut off its lead-in (faster-whisper on the CPU).

  <chatterbox python> check_take.py <take.wav> <expected.txt> [number of lead-in words] [out.wav]
  -> prints one JSON line: ok, reasons, ratio, lost, extra, first, cut_s, heard

Why a lead-in: OmniVoice often garbles the very first syllables of a generation ("T'es pas le client" came out as
"Toi, le client"). omni_units.py therefore starts every unit with a throwaway sentence; here it is cut off at the
first real silence of the sound (see find_cut: whisper alone is not enough, it sometimes does not write the lead-in
and the lead-in then stayed in the take), and the cut result is transcribed again to check how it starts.

A take is ok when: the first real words are right, no run of 4+ words is missing (a skipped sentence), no run of 5+
extra words, and at least 88 % of the words match. Numbers are ignored on both sides (whisper writes "10", "2h",
"1 000" where the script says "dix", "deux heures", "mille").
"""
import difflib
import json
import re
import sys
import unicodedata
from pathlib import Path

import numpy as np
import soundfile as sf

NUM = set("zéro un une deux trois quatre cinq six sept huit neuf dix onze douze treize quatorze quinze seize vingt "
          "trente quarante cinquante soixante cent cents mille".split())


def norm(text):
    t = text.lower().replace("’", "'")
    t = re.sub(r"\[[a-z-]+\]", " ", t)              # OmniVoice tags like [sigh]
    t = re.sub(r"(\d+)\s*h\b", " heures ", t)
    t = re.sub(r"\d+", " ", t)
    t = re.sub(r"[^a-zàâäçéèêëîïôöùûüÿœæ']", " ", t)
    out = []
    for w in t.split():
        out += [x for x in w.split("'") if x and x not in NUM]
    return ["t" if w == "tu" else w for w in out]   # whisper writes "tu es" for a spoken "t'es"


def sound(word):
    """What a written French word sounds like, roughly: silent endings removed, so that homophones whisper may pick
    instead of the script's spelling count as the same word ("leurs conseils préférés" = "leur conseil préféré",
    "regardez" = "regarde", "sort" = "sors"). A garbled or missing word still differs."""
    w = "".join(ch for ch in unicodedata.normalize("NFD", word) if unicodedata.category(ch) != "Mn")
    if len(w) > 4 and w.endswith("ent"):
        w = w[:-2]
    w = w.rstrip("sxztd") or w
    if len(w) > 2 and w.endswith("e"):
        w = w[:-1]
    return w.rstrip("sxztd") or w


def transcribe(model, path):
    segs, _ = model.transcribe(str(path), language="fr", word_timestamps=True, vad_filter=False,
                               condition_on_previous_text=False, beam_size=5)
    heard, text = [], []
    for s in segs:
        text.append(s.text.strip())
        for w in s.words:
            heard += [(sound(tok), w.start, w.end) for tok in norm(w.word)]
    return heard, " ".join(text)


def compare(exp, heard):
    m = difflib.SequenceMatcher(None, exp, heard, autojunk=False)
    lost = extra = 0
    for op, i1, i2, j1, j2 in m.get_opcodes():
        if op in ("delete", "replace"):
            lost = max(lost, (i2 - i1) - (j2 - j1))
        if op in ("insert", "replace"):
            extra = max(extra, (j2 - j1) - (i2 - i1))
    return m, round(m.ratio(), 3), lost, extra


def starts_right(real, heard):
    """At least 3 of the first 4 real words are among the first 6 heard words, in order."""
    want, got, k = real[:4], heard[:6], 0
    for w in got:
        if k < len(want) and w == want[k]:
            k += 1
        elif k + 1 < len(want) and w == want[k + 1]:   # one word may be missing or spelled differently
            k += 2
    return k >= min(3, len(want))


def find_cut(x, sr, hint=None):
    """Sample where the lead-in ends, found by ear-of-machine on the sound itself, not on whisper's word list
    (whisper sometimes does not write the lead-in at all, and then it stayed in the take).
    The lead-in ends at a real silence: at least 80 ms, 26 dB under the loudest moment, that comes 0.25 s or more
    after the voice starts, within the first 2.2 s. hint = where whisper puts that boundary (seconds), used to
    pick between several silences; without it the first one is taken. Returns None when there is no such silence.
    """
    frame = int(0.01 * sr)
    db_all = np.array([10 * np.log10(np.mean(x[i:i + frame] ** 2) + 1e-12) for i in range(0, len(x) - frame, frame)])
    db = db_all[:220]
    loud = np.where(db > db_all.max() - 20)[0]
    if not len(loud):
        return None
    quiet, runs, i = db < db_all.max() - 26, [], loud[0]
    while i < len(db):
        if quiet[i]:
            j = i
            while j + 1 < len(db) and quiet[j + 1]:
                j += 1
            if j - i + 1 >= 8 and i >= loud[0] + 25:
                runs.append((i + j + 1) / 2 * frame / sr)   # centre of the silence, in seconds
            i = j + 1
        else:
            i += 1
    if not runs:
        return None
    if hint is None:
        return int(runs[0] * sr)
    best = min(runs, key=lambda t: abs(t - hint))
    return int(best * sr) if abs(best - hint) <= 0.4 else None


def main(wav, expected_file, n_lead="0", out=""):
    from faster_whisper import WhisperModel

    n_lead = int(n_lead)
    exp = [sound(w) for w in norm(Path(expected_file).read_text(encoding="utf-8"))]
    model = WhisperModel("small", device="cpu", compute_type="int8")
    heard, text = transcribe(model, wav)
    tokens = [h[0] for h in heard]
    m, ratio, lost, extra = compare(exp, tokens)
    res = {"ok": False, "reasons": [], "ratio": ratio, "lost": lost, "extra": extra, "heard": text}

    # where does the real text start in what was heard?
    first = None
    for a, b, size in m.get_matching_blocks():
        if size and a + size > n_lead:
            first = b + (n_lead - a) if a <= n_lead else max(0, b - (a - n_lead))
            break
    if first is None:
        res["reasons"].append("nothing recognisable")
        print(json.dumps(res, ensure_ascii=False))
        return
    res["first"] = starts_right(exp[n_lead:], tokens[first:])
    if not res["first"]:
        res["reasons"].append("first words wrong: " + " ".join(tokens[first:first + 5]))
    if lost >= 4:
        res["reasons"].append(f"{lost} words missing in a row")
    if extra >= 5:
        res["reasons"].append(f"{extra} extra words in a row")
    if ratio < 0.88:
        res["reasons"].append(f"only {round(100 * ratio)} % of the words match")

    x, sr = sf.read(wav, dtype="float32")
    x = x.mean(axis=1) if x.ndim == 2 else x
    if n_lead and not res["reasons"]:
        # whisper's idea of the boundary, only when it actually wrote the lead-in before the first real word
        hint = (heard[first - 1][2] + heard[first][1]) / 2 if first > 0 else None
        cut = find_cut(x, sr, hint)
        if cut is None:
            res["reasons"].append("no clean silence between the lead-in and the text")
        else:
            res["cut_s"] = round(cut / sr, 2)
            res["lead_in_heard"] = hint is not None
            x = x[cut:].copy()
            x[:int(0.004 * sr)] *= np.linspace(0, 1, int(0.004 * sr), dtype=np.float32)
    if out and not res["reasons"]:
        sf.write(out, x, sr)
        if n_lead:   # second look: the cut take must say the real text, with nothing left of the lead-in
            heard2, text2 = transcribe(model, out)
            tok2 = [h[0] for h in heard2]
            _, ratio2, lost2, extra2 = compare(exp[n_lead:], tok2)
            res.update(ratio=ratio2, lost=lost2, extra=extra2, heard=text2)
            real = exp[n_lead:]
            leftover = tok2[:1] and tok2[0] in exp[:n_lead] and tok2[0] not in real[:2]
            if not starts_right(real, tok2) or leftover or not set(tok2[:2]) & set(real[:2]):
                res["reasons"].append("after the cut the start is wrong: " + " ".join(tok2[:5]))
            if lost2 >= 4 or extra2 >= 5 or ratio2 < 0.88:
                res["reasons"].append(f"after the cut: {round(100 * ratio2)} % match, {lost2} missing, {extra2} extra")
            if res["reasons"]:
                Path(out).unlink()
    res["ok"] = not res["reasons"]
    print(json.dumps(res, ensure_ascii=False))


if __name__ == "__main__":
    main(*sys.argv[1:5])

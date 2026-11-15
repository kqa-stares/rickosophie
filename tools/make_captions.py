"""Captions for a voice track: the script's own words (never whisper's spelling), timed on the voice.

  cd tools && PYTHONUTF8=1 C:/Users/wqach/chatterbox/.venv/Scripts/python.exe make_captions.py <voice.wav> <script.txt> <out folder>

whisper gives the time of every word it hears; the script words are matched to them (same matching as check_take.py),
and a word whisper wrote differently (numbers, "scrolle") gets its time from its neighbours.
Style copied from the reference channel: small white text with a black outline in the middle of the picture,
a few words at a time, one or two lines, cut at the punctuation.
Writes words.json (each script word with start/end), captions.json (the chunks) and captions.ass (for FFmpeg).
"""
import difflib
import json
import sys
from pathlib import Path

from check_take import norm

MAX_CHARS = 34      # per caption
LINE_CHARS = 24     # above this the caption goes on two lines
FONT, SIZE, Y = "Open Sans", 96, 930   # bold, on a 1080x1920 picture: letters as big as the reference channel's
FONT_FILE = str(Path(__file__).resolve().parent.parent / "assets" / "fonts" / "OpenSans-Bold.ttf")    # the same font in bold, to measure the lines
MAX_WIDTH = 940                                # pixels; a wider line is set smaller
CENSOR = {"putain": "p*tain", "putains": "p*tains", "merde": "m*rde", "connards": "c*nnards", "connard": "c*nnard"}


def word_times(voice, script_words):
    from faster_whisper import WhisperModel
    model = WhisperModel("small", device="cpu", compute_type="int8")
    segs, _ = model.transcribe(str(voice), language="fr", word_timestamps=True, vad_filter=False,
                               condition_on_previous_text=False, beam_size=5)
    heard = [(tok, w.start, w.end) for s in segs for w in s.words for tok in norm(w.word)]
    flat = [(tok, i) for i, w in enumerate(script_words) for tok in norm(w)]
    m = difflib.SequenceMatcher(None, [t for t, _ in flat], [h[0] for h in heard], autojunk=False)
    times = [None] * len(script_words)
    for a, b, size in m.get_matching_blocks():
        for k in range(size):
            i, (_, s, e) = flat[a + k][1], heard[b + k]
            times[i] = (min(s, times[i][0]), max(e, times[i][1])) if times[i] else (s, e)
    total = heard[-1][2] if heard else 0.0
    # words without a time: share the gap between their timed neighbours, by length
    i = 0
    while i < len(times):
        if times[i] is None:
            j = i
            while j < len(times) and times[j] is None:
                j += 1
            left = times[i - 1][1] if i else 0.0
            right = times[j][0] if j < len(times) else total
            lens = [len(script_words[k]) + 1 for k in range(i, j)]
            t = left
            for k, n in zip(range(i, j), lens):
                step = (right - left) * n / sum(lens)
                times[k] = (t, t + step)
                t += step
            i = j
        else:
            i += 1
    out, last = [], 0.0
    for w, (s, e) in zip(script_words, times):     # keep the times in order
        s = max(s, last)
        e = max(e, s + 0.04)
        out.append({"word": w, "start": round(s, 3), "end": round(e, 3)})
        last = s
    return out


WEAK = set("de du des le la les l un une à au aux et ou que qu qui ton ta tes te t tu il ils on en pour par sur dans "
           "est a as c ce ça se s ne n pas plus y d je j me m son sa ses leur leurs avec comme si mais "
           "deux trois quatre cinq six sept huit neuf dix vingt cent mille".split())


def text_of(ws):
    return " ".join(x["word"] for x in ws)


def is_weak(w):
    return w["word"].lower().strip(".,?!:;").split("'")[-1] in WEAK or w["word"].endswith("'")


def split_phrase(ws):
    """One phrase (no strong punctuation inside) -> captions of at most about MAX_CHARS, cut in two as evenly as
    possible, again and again: never after a small word ("de ton" / "téléphone." became "T'es pas le client" /
    "de ton téléphone."), preferably at a comma, never leaving a scrap of a word or two ("zone" / "de confort")."""
    if len(text_of(ws)) <= MAX_CHARS + 2 or len(ws) < 2:
        return [ws]
    best, best_score = 1, None
    for k in range(1, len(ws)):
        a, b = text_of(ws[:k]), text_of(ws[k:])
        score = abs(len(a) - len(b)) + (40 if is_weak(ws[k - 1]) else 0) + (25 if min(len(a), len(b)) < 10 else 0) \
            - (8 if ws[k - 1]["word"].endswith(",") else 0)
        if best_score is None or score < best_score:
            best, best_score = k, score
    return split_phrase(ws[:best]) + split_phrase(ws[best:])


_MEASURE = []


def measure():
    """The caption font at the size the subtitle renderer really draws it, to measure lines in pixels.
    In .ass files the size is the height of a whole line (ascent + descent), not the letter size PIL uses:
    for Segoe UI that is 1.33 times smaller letters, so measuring at SIZE made every line look a third too wide."""
    if not _MEASURE:
        from PIL import ImageFont
        ascent, descent = ImageFont.truetype(FONT_FILE, SIZE).getmetrics()
        _MEASURE.append(ImageFont.truetype(FONT_FILE, round(SIZE * SIZE / (ascent + descent))))
    return _MEASURE[0]


def censor(word):
    """'Putain,' -> 'P*tain,' (keeps the capital and the punctuation)."""
    core = word.strip(".,?!:; ")
    rep = CENSOR.get(core.lower())
    if not rep:
        return word
    if core[:1].isupper():
        rep = rep[0].upper() + rep[1:]
    return word.replace(core, rep, 1)


def chunks(words):
    # French writes "ça ?" and "dis-moi :" with a space: glue the lone mark to its word first
    ws = []
    for w in words:
        if w["word"] in ("?", "!", ":", ";") and ws:
            ws[-1] = {**ws[-1], "word": ws[-1]["word"] + (" " + w["word"] if w["word"] in "?!" else ""), "end": w["end"]}
        else:
            ws.append(dict(w))
    phrases, cur = [], []
    for w in ws:
        cur.append(w)
        end = w["word"][-1]
        if end in ".?!…" or (end == "," and len(text_of(cur)) >= 14):
            phrases.append(cur)
            cur = []
    if cur:
        phrases.append(cur)
    caps = []
    for p in phrases:
        for part in split_phrase(p):
            # a very short caption ("hein.", "Bravo.") joins the one before when they belong to the same breath
            if caps and len(text_of(part)) <= 9 and len(text_of(caps[-1] + part)) <= MAX_CHARS \
                    and part[0]["start"] - caps[-1][-1]["end"] < 0.35 and caps[-1][-1]["word"][-1] not in ".?!…":
                caps[-1] = caps[-1] + part
            else:
                caps.append(part)
    out = []
    for k, c in enumerate(caps):
        text = " ".join(censor(x["word"]) for x in c).rstrip(",")
        nxt = caps[k + 1][0]["start"] if k + 1 < len(caps) else c[-1]["end"] + 0.4
        end = nxt if nxt - c[-1]["end"] < 0.6 else c[-1]["end"] + 0.25
        out.append({"start": 0.0 if k == 0 else c[0]["start"], "end": round(end, 3), "text": text})
    return out


def two_lines(text):
    """One line when it fits the picture, else two lines of about the same width (so the letter size never changes)."""
    m = measure()
    if m.getlength(text) <= MAX_WIDTH or " " not in text:
        return text
    spaces = [i for i, ch in enumerate(text) if ch == " " and text[i + 1:i + 2] not in "?!:"]
    cut = min(spaces or [text.index(" ")], key=lambda i: abs(m.getlength(text[:i]) - m.getlength(text[i + 1:])))
    return text[:cut] + r"\N" + text[cut + 1:]


def ass_time(t):
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def apply_display(words, mapping):
    """Show some spoken words differently: {"neuf cent quatre-vingt-dix-sept euros": "997 euros"} turns those words
    into one caption word timed from the first to the last. Spoken numbers read faster as digits."""
    keys = [(k.lower().split(), v) for k, v in mapping.items() if not k.startswith("_")]
    out, i = [], 0
    while i < len(words):
        for k, v in keys:
            seg = [w["word"].lower().strip(".,?!:;") for w in words[i:i + len(k)]]
            if seg == k:
                last = words[i + len(k) - 1]["word"]
                out.append({"word": v + last[len(last.rstrip(".,?!:;")):], "start": words[i]["start"],
                            "end": words[i + len(k) - 1]["end"]})
                i += len(k)
                break
        else:
            out.append(words[i])
            i += 1
    return out


def write_ass(caps, path, offset=0.0):
    """captions -> .ass file for FFmpeg, every time moved by offset seconds. Returns the widest line in pixels."""
    head = ("[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\nWrapStyle: 2\nScaledBorderAndShadow: yes\n\n"
            "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, "
            "Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
            "MarginR, MarginV, Encoding\n"
            f"Style: Cap,{FONT},{SIZE},&H00FFFFFF,&H00FFFFFF,&H00000000,&H78000000,-1,0,0,0,100,100,0,0,1,5,1.5,5,60,60,0,1\n\n"
            "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
    lines, widest = [], 0
    for c in caps:
        text = two_lines(c["text"])
        width = max(measure().getlength(part) for part in text.split(r"\N"))
        widest = max(widest, width)
        size = f"{{\\fs{int(SIZE * MAX_WIDTH / width)}}}" if width > MAX_WIDTH else ""
        start = c["start"] + offset if c["start"] > 0 else offset
        lines.append(f"Dialogue: 0,{ass_time(start)},{ass_time(c['end'] + offset)},Cap,,0,0,0,,"
                     f"{{\\pos(540,{Y})}}{size}{text}")
    Path(path).write_text(head + "\n".join(lines) + "\n", encoding="utf-8")
    return widest


def main(voice, script, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    script_words = Path(script).read_text(encoding="utf-8").split()
    if voice == "-":      # only cut the captions again, from the word times already found
        words = json.loads((out / "words.json").read_text(encoding="utf-8"))
    else:
        words = word_times(voice, script_words)
    display = out / "display.json"
    if display.exists():
        words = apply_display(words, json.loads(display.read_text(encoding="utf-8")))
    caps = chunks(words)
    (out / "words.json").write_text(json.dumps(words, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "captions.json").write_text(json.dumps(caps, ensure_ascii=False, indent=1), encoding="utf-8")
    widest = write_ass(caps, out / "captions.ass")
    print(f"widest line {widest:.0f} px of {MAX_WIDTH}")
    print(len(words), "words,", len(caps), "captions, longest", max(len(c["text"]) for c in caps), "characters")
    for c in caps:
        print(f"  {c['start']:6.2f} - {c['end']:6.2f}  {c['text']}")


if __name__ == "__main__":
    main(*sys.argv[1:4])

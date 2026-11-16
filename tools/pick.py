"""Choose one picture per sentence among the hand-verified clips (assets/private/clips.json + vectors.npy).

  python tools/pick.py <work folder> <images file> <script file>

Every clip was checked by eye (Rick from the front, big, centred in the 4:5 crop: the owner's three complaints were
cut framing, pictures unrelated to the words, scene changes at bad moments). The images file gives, per unit of the
script, short English descriptions separated by "|"; CLIP (text side only: the clips' vectors are precomputed)
matches each description with every clip. The picture changes at sentence ends only, every 1.8 to 5 s.
A clip is used once per video and not again for the next 200 picks (state.json -> recent_clips).
Writes <work folder>/edit.json for make_video.py.
"""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import torch
from transformers import CLIPModel, CLIPProcessor

from make_video import LEAD, TAIL, stable_range

ROOT = Path(__file__).resolve().parent.parent
PRIVATE = ROOT / "assets" / "private"
MIN_SHOT, MAX_SHOT, RECENT = 1.8, 5.0, 200


def shots_from(caps, total):
    """Cut points at sentence ends; short sentences are merged, long ones split at a caption boundary."""
    ends = [c["end"] for c in caps if c["text"].rstrip()[-1:] in ".?!…"]
    cuts, last = [0.0], 0.0
    for e in ends:
        if e - last >= MIN_SHOT and total - e >= MIN_SHOT:
            cuts.append(e)
            last = e
    out = []
    for a, b in zip(cuts, cuts[1:] + [total]):
        while b - a > MAX_SHOT:
            inner = [c["end"] for c in caps if a + MIN_SHOT <= c["end"] <= b - MIN_SHOT]
            if not inner:
                break
            m = min(inner, key=lambda t: abs(t - (a + min(3.2, (b - a) / 2))))
            out.append(a)
            a = m
        out.append(a)
    return sorted(set(round(t, 2) for t in out))


def main(folder, images_file, script_file):
    folder = Path(folder)
    caps = json.loads((folder / "captions.json").read_text(encoding="utf-8"))
    words = json.loads((folder / "words.json").read_text(encoding="utf-8"))
    units = [l.split() for l in Path(script_file).read_text(encoding="utf-8").splitlines() if l.strip()]
    hints = [[h.strip() for h in l.split("|") if h.strip()]
             for l in Path(images_file).read_text(encoding="utf-8").splitlines() if l.strip()]
    if len(hints) != len(units):
        sys.exit(f"{images_file} has {len(hints)} lines for {len(units)} units")
    total = words[-1]["end"]
    starts, done, n = [], 0, sum(len(u) for u in units)
    for u in units:
        t = words[min(len(words) - 1, round(done / n * len(words)))]["start"]
        starts.append(min((c["start"] for c in caps), key=lambda s: abs(s - t)) if done else 0.0)
        done += len(u)
    times = shots_from(caps, total)

    clips = json.loads((PRIVATE / "clips.json").read_text(encoding="utf-8"))
    V = np.load(PRIVATE / "vectors.npy").astype(np.float32)
    state_file = ROOT / "state.json"
    state = json.loads(state_file.read_text(encoding="utf-8")) if state_file.exists() else {}
    recent = set(state.get("recent_clips", []))
    # clips showing opening credits (names on screen): never used
    banned = set(json.loads((ROOT / "assets" / "banned_clips.json").read_text(encoding="utf-8")))
    clips = [c if c["file"] not in banned else dict(c, dur=0) for c in clips]

    model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32").eval()
    proc = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
    flat = sorted({h for hs in hints for h in hs})
    with torch.no_grad():
        out = model.get_text_features(**proc(text=[f"Rick and Morty cartoon, {h}" for h in flat], return_tensors="pt", padding=True))
        T = (out if torch.is_tensor(out) else out.pooler_output).numpy()
    T = T / np.linalg.norm(T, axis=1, keepdims=True)

    used, shots, count = [], [], {}
    for i, t in enumerate(times):
        end = times[i + 1] if i + 1 < len(times) else total + TAIL
        need = end - t + (LEAD if i == 0 else 0)
        u = max(k for k, s in enumerate(starts) if s <= t + 0.05)
        hint = hints[u][count.get(u, 0) % len(hints[u])]
        count[u] = count.get(u, 0) + 1
        score = V @ T[flat.index(hint)]
        for k in np.argsort(-score):
            c = clips[k]
            if c["file"] in used or (c["file"] in recent and len(recent) < len(clips) - 40) or c["dur"] < need + 0.15:
                continue
            a, b = stable_range(PRIVATE / "clips" / c["file"], 0.04, c["dur"] - 0.04, c["dur"] / 2, limit=0.045)
            if b - a < need + 0.05:
                continue
            used.append(c["file"])
            src = min(max(a, c["dur"] / 2 - need / 2), b - need - 0.02)
            shots.append({"t": t, "file": c["file"], "start": round(max(0.0, src), 2), "cx": c["cx"],
                          "why": f"{hint} ({score[k]:.2f})"})
            break
        else:
            sys.exit(f"no clip long enough for the picture at {t:.1f} s ({need:.1f} s, '{hint}')")
    (folder / "picked.json").write_text(json.dumps(used), encoding="utf-8")
    edit = json.loads((folder / "edit.json").read_text(encoding="utf-8")) if (folder / "edit.json").exists() else {}
    edit["shots"] = shots
    (folder / "edit.json").write_text(json.dumps(edit, ensure_ascii=False, indent=1), encoding="utf-8")
    print(len(shots), "pictures chosen")


if __name__ == "__main__":
    main(*sys.argv[1:4])

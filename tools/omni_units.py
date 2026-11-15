"""OmniVoice, the reliable way: the script is generated unit by unit (one line of the script file = one unit of
2 to 6 sentences, 9 to 13 s), and every unit is checked by ear-of-machine (whisper) and redone until it is right.

  cd tools && PYTHONUTF8=1 C:/Users/wqach/omnivoice/.venv/Scripts/python.exe omni_units.py ../scripts/telephone.txt [speed] [seeds] [units]

Why units: OmniVoice is built for chunks of about 15 s; asked for 34 s in one go it skipped a whole sentence.
Why a lead-in: it garbles the very first syllables of a generation, so each unit starts with a throwaway sentence
that check_take.py cuts off. Why a check: a wrong take is redone with the next seed instead of reaching the listener.
[seeds] = "2,3,4,5" (tried in this order until a take passes). [units] = "1,4" to redo only those.
Writes tests/<script name>/part_N.wav (24 kHz, lead-in removed) + raw/ (every take as generated) + takes.json.
Then: join_parts.py glues the parts into voix.wav.
"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import soundfile as sf
import torch
from omnivoice import OmniVoice

ROOT = Path(__file__).resolve().parent.parent
PRIVATE = ROOT / "assets" / "private"
DEVICE = "cuda:0" if torch.cuda.is_available() else "cpu"

LEAD = "Écoute-moi bien."
N_LEAD = 3  # words of LEAD once normalised by check_take.py
GOOD = 0.95  # a take this good is kept at once; an ok take under it ("arnaque chimique" heard as "arme chimique",
#              0.925) only counts if no other seed does better
CHECK_PY = os.environ.get("CHECK_PY", sys.executable)   # Python with faster-whisper


def check(raw, sent, out):
    expected = raw.with_suffix(".txt")
    expected.write_text(sent, encoding="utf-8")
    r = subprocess.run([CHECK_PY, str(Path(__file__).with_name("check_take.py")), str(raw), str(expected), str(N_LEAD), str(out)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL)
    lines = [l for l in r.stdout.splitlines() if l.startswith("{")]
    if not lines:
        return {"ok": False, "reasons": ["check failed: " + r.stderr[-300:]], "ratio": 0, "heard": ""}
    return json.loads(lines[-1])


def main(script, speed="0.88", seeds="2,3,4,5", units=""):
    script = Path(script).resolve()
    speed, seeds = float(speed), [int(s) for s in seeds.split(",")]
    lines = [" ".join(l.split()) for l in script.read_text(encoding="utf-8").splitlines() if l.strip()]
    only = {int(x) for x in units.split(",") if x} or set(range(1, len(lines) + 1))
    out = ROOT / "tests" / script.stem
    (out / "raw").mkdir(parents=True, exist_ok=True)
    takes_file = out / "takes.json"
    takes = {t["file"]: t for t in json.loads(takes_file.read_text(encoding="utf-8"))} if takes_file.exists() else {}

    model = OmniVoice.from_pretrained("k2-fsa/OmniVoice", device_map=DEVICE,
                                      dtype=torch.float16 if DEVICE != "cpu" else torch.float32)
    ref_audio = PRIVATE / "voice" / "reference.wav"
    ref_text = (PRIVATE / "voice" / "reference.txt").read_text(encoding="utf-8")
    prompt = model.create_voice_clone_prompt(ref_audio=str(ref_audio), ref_text=ref_text)
    for n, text in enumerate(lines, 1):
        if n not in only:
            continue
        name, sent, tries, best, best_ratio = f"part_{n}.wav", f"{LEAD} {text}", [], None, 0.0
        (out / name).unlink(missing_ok=True)
        t0 = time.time()
        for seed in seeds:
            raw = out / "raw" / f"unit_{n}_s{seed}.wav"
            cut = out / "raw" / f"cut_{n}_s{seed}.wav"
            torch.manual_seed(seed)
            audio = model.generate(text=sent, voice_clone_prompt=prompt, num_step=32, speed=speed,
                                   fade_duration=0.02, pad_duration=0.15, postprocess_output=True)
            sf.write(raw, audio[0], 24000)
            res = check(raw, sent, cut)
            tries.append({"seed": seed, **{k: res.get(k) for k in ("ok", "ratio", "reasons", "cut_s", "heard")}})
            print(f"unit {n} seed {seed}: {'OK' if res['ok'] else 'redo'} ratio {res.get('ratio')} {res.get('reasons')}", flush=True)
            if res["ok"] and res["ratio"] > best_ratio:
                best, best_ratio = seed, res["ratio"]
            if res["ok"] and res["ratio"] >= GOOD:
                break
        if best is not None:
            shutil.copyfile(out / "raw" / f"cut_{n}_s{best}.wav", out / name)
        takes[name] = {"file": name, "line": f"partie {n}", "mode": f"vitesse {speed}", "text": text, "words": len(text.split()),
                       "ok": best is not None, "seed": best, "tries": tries, "gen_s": round(time.time() - t0, 1),
                       "dur": round(sf.info(out / name).duration, 1) if best is not None else None}
        takes_file.write_text(json.dumps([takes[k] for k in sorted(takes)], ensure_ascii=False, indent=1), encoding="utf-8")
    bad = [k for k, t in takes.items() if not t["ok"]]
    print("ALL UNITS OK" if not bad else f"NOT OK: {bad}", flush=True)
    if bad:
        sys.exit(f"voice: units {bad} could not be said correctly")


if __name__ == "__main__":
    main(*sys.argv[1:5])

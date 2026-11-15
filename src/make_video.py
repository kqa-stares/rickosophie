"""One Rickosophie video, from a topic of topics.json to output/<id>/video.mp4.

Chain (each step is a tool of tools/, tested on the owner's PC before):
  1. voice: OmniVoice says the script unit by unit, every unit heard back by whisper and redone if wrong
     (tools/omni_units.py), the units are joined (join_parts.py), then Rick's trained timbre goes on top (rvc.py)
  2. captions: the script's own words timed on the voice (make_captions.py)
  3. pictures: one hand-verified clip per sentence, matched to the topic's image descriptions (pick.py)
  4. montage: crop 4:5 over a blurred copy, banner, captions, music under the voice (make_video.py)
Python for each step: PY_VOICE (OmniVoice + whisper + CLIP), PY_APPLIO (Applio). Both default to this Python.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

from common import OUTPUT, ROOT, STATE_FILE, load_config, load_json

TOOLS = ROOT / "tools"
MUSIC = ROOT / "assets" / "music"


def run(python, *args, cwd=TOOLS, env=None):
    cmd = [python, *map(str, args)]
    print("  $", " ".join(Path(c).name if os.sep in c or "/" in c else c for c in cmd[:3]), flush=True)
    r = subprocess.run(cmd, cwd=cwd, env={**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8", **(env or {})},
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    tail = "\n".join(l for l in (r.stdout + r.stderr).splitlines() if "Warning" not in l and "it/s]" not in l)[-1500:]
    print(tail, flush=True)
    if r.returncode:
        raise SystemExit(f"{Path(args[0]).name} failed: {tail[-400:]}")
    return r.stdout


def pick_topic(lang, topic_id=None, exclude=()):
    topics = load_json(ROOT / "topics.json", [])
    if topic_id:
        return next(t for t in topics if t["id"] == topic_id)
    used = set(load_json(STATE_FILE, {}).get(lang, [])) | set(exclude)
    unused = [t for t in topics if t["id"] not in used and lang in t.get("lines", {})]
    if unused:
        return unused[0]
    raise SystemExit(f"No unused '{lang}' topics left in topics.json. Ask Claude to write the next batch.")


def music_track(topic_id):
    """One of the owner's six tracks (assets/music/tracks.json), downloaded from Pixabay at run time: their licence
    forbids passing the files on as they are, so they are never stored in this public repository."""
    tracks = load_json(MUSIC / "tracks.json")["tracks"]
    t = tracks[int(hashlib.md5(topic_id.encode()).hexdigest(), 16) % len(tracks)]
    path = MUSIC / f"{t['id']}.mp3"
    if not path.exists():
        req = urllib.request.Request(t["url"], headers={"User-Agent": "Mozilla/5.0"})
        path.write_bytes(urllib.request.urlopen(req, timeout=120).read())
    return path


def make_video(lang, topic_id=None, exclude=()):
    topic = pick_topic(lang, topic_id, exclude)
    name = topic["id"]
    py_voice = os.environ.get("PY_VOICE", sys.executable)
    py_applio = os.environ.get("PY_APPLIO", sys.executable)
    print(f"\n[{lang}] {name}: {topic['title'][lang]}", flush=True)
    scripts = ROOT / "scripts"
    scripts.mkdir(exist_ok=True)
    script = scripts / f"{name}.txt"
    script.write_text("\n".join(topic["lines"][lang]) + "\n", encoding="utf-8")
    images = scripts / f"{name}.images.txt"
    images.write_text("\n".join(topic["images"]) + "\n", encoding="utf-8")

    tests = ROOT / "tests" / name
    shutil.rmtree(tests, ignore_errors=True)
    run(py_voice, "omni_units.py", script, "0.88", "2,3,4,5", env={"CHECK_PY": py_voice})
    run(py_voice, "join_parts.py", tests, "pause=0.42")
    folder = OUTPUT / name
    folder.mkdir(parents=True, exist_ok=True)
    voice = folder / "voice.wav"
    run(py_applio, TOOLS / "rvc.py", tests / "voix.wav", voice, cwd=ROOT)
    run(py_voice, "make_captions.py", voice, script, folder)
    edit = {"voice": str(voice), "music": str(music_track(name)), "music_start": 8, "shots": []}
    (folder / "edit.json").write_text(json.dumps(edit, ensure_ascii=False), encoding="utf-8")
    run(py_voice, "pick.py", folder, images, script)
    out = run(py_voice, "make_video.py", folder)
    check = json.loads((folder / "check" / "info.json").read_text(encoding="utf-8"))
    config = load_config()
    tags = " ".join(dict.fromkeys(topic.get("hashtags", "").split() + config["languages"][lang].get("hashtags", "").split()))
    caption = f"{topic['caption']} {config['languages'][lang].get('caption_emoji', '')}\n\n" \
              f"{config['languages'][lang].get('comment_prompt', '')}\n\n{tags}".strip()
    return {"lang": lang, "topic_id": name, "ai_generated": True, "title": topic["title"][lang], "video": str(folder / "video.mp4"),
            "seconds": check["seconds"], "caption": caption,
            "clips": json.loads((folder / "picked.json").read_text(encoding="utf-8"))}


def remember(clip_files):
    """Clips shown recently are not chosen again for the next 200 picks (tools/pick.py)."""
    from common import save_json
    state = load_json(STATE_FILE, {})
    state["recent_clips"] = (state.get("recent_clips", []) + list(clip_files))[-200:]
    save_json(STATE_FILE, state)


if __name__ == "__main__":
    print(json.dumps(make_video("fr", sys.argv[1] if len(sys.argv) > 1 else None), ensure_ascii=False, indent=1))

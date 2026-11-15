"""Assemble one video in the reference channel's format: series clips cropped 4:5 over a blurred copy of themselves,
the channel banner above the picture, small captions in the middle of it, the voice, soft music under it.

  cd tools && PYTHONUTF8=1 C:/Users/wqach/chatterbox/.venv/Scripts/python.exe make_video.py ../videos/telephone

Reads <folder>/edit.json (which picture goes with which words, see its _help) and captions.json (make_captions.py).
The voice starts after a short lead-in (LEAD seconds of picture, banner and music): the owner found a first word on
the very first frame too abrupt. Times in edit.json and captions.json stay relative to the voice.
Writes <folder>/video.mp4 (1080x1920, 25 pictures a second, like most of the source files) and <folder>/check/:
one frame per shot on a contact sheet, plus the numbers (length, loudness).
A clip a little too short for its words is slowed down (never more than 25 %).
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from make_captions import write_ass

ROOT = Path(__file__).resolve().parent.parent
FPS = 25
VOICE_LUFS, MUSIC_UNDER = -13.5, 17.0    # the music sits 17 dB under the voice (reference channel: 10 to 20);
#                                          the finished video then measures about -14 LUFS, the level the platforms use
TOP = (1920 - 1350) // 2                 # where the 1080x1350 picture starts
LEAD, TAIL = 0.6, 0.7                    # seconds of picture and music before the first word and after the last one
BRAND = ROOT / "assets" / "brand" / "overlay.png"
CLIPS = ROOT / "assets" / "private" / "clips"
FONTS = ROOT / "assets" / "fonts"   # tools/make_brand.py


def run(cmd, **kw):
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, encoding="utf-8", errors="replace",
                       stdin=subprocess.DEVNULL, **kw)
    if r.returncode:
        sys.exit("ffmpeg failed:\n" + r.stderr[-2500:])
    return r.stderr


def seconds(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True).stdout.strip()
    return float(out)


def lufs(path, start=None, dur=None):
    cmd = ["ffmpeg", "-hide_banner", "-nostats"]
    if start is not None:
        cmd += ["-ss", start, "-t", dur]
    log = run(cmd + ["-i", path, "-af", "ebur128", "-f", "null", "-"])
    return float(re.findall(r"I:\s*(-?[\d.]+) LUFS", log)[-1])


def small_frames(path, start, dur, fps=12.5):
    raw = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", f"{start:.3f}", "-t", f"{dur:.3f}",
                          "-i", str(path), "-an", "-vf", f"fps={fps},scale=48:27,format=gray", "-f", "rawvideo", "-"],
                         capture_output=True, stdin=subprocess.DEVNULL).stdout
    n = len(raw) // (48 * 27)
    return np.frombuffer(raw[:n * 48 * 27], np.uint8).reshape(n, 27, 48).astype(np.float32) / 255


def stable_range(path, start, end, ref_t, limit=0.07, fps=12.5):
    """Source seconds around ref_t (the frame reviewed on the contact sheet, the clip's middle) where the picture stays
    close to that frame. Cut detection misses slow camera moves: clip 10 pulls back from Rick to a dragon, and that
    dragon ended up under 'Et quand ça marche pas'. Same shot: mean difference under 0.05; another view: over 0.13."""
    f = small_frames(path, start, end - start, fps)
    if not len(f):
        return start, end
    k = min(len(f) - 1, max(0, int(round((ref_t - start) * fps))))
    d = np.abs(f - f[k]).mean(axis=(1, 2))
    a = b = k
    while a > 0 and d[a - 1] <= limit:
        a -= 1
    while b < len(f) - 1 and d[b + 1] <= limit:
        b += 1
    return start + a / fps, min(end, start + (b + 1) / fps)


def main(folder):
    folder = Path(folder).resolve()
    edit = json.loads((folder / "edit.json").read_text(encoding="utf-8"))
    clips = {}   # this repository only uses scene mode: each shot names its clip file and start
    sources = {}
    voice = (folder / edit["voice"]).resolve()
    lead = edit.get("lead", LEAD)
    total = round(lead + seconds(voice) + TAIL, 2)
    parts = folder / "parts"
    parts.mkdir(exist_ok=True)
    shots = edit["shots"]
    listing = []
    total = round(total * FPS) / FPS
    for i, s in enumerate(shots):
        # whole frames, counted from the start of the video: parts cut at -t rounded each one and the pictures
        # drifted 0.24 s behind the words by the end
        first = 0 if i == 0 else round((lead + s["t"]) * FPS)
        last = round((lead + shots[i + 1]["t"]) * FPS) if i + 1 < len(shots) else round(total * FPS)
        frames, begin = last - first, first / FPS
        need = frames / FPS
        if "file" in s:
            # scene mode (auto_scene.py): a long continuous passage of one source file, played as it is, cuts included,
            # like the reference channel does. Centre crop: it stays clear of both logo corners.
            c = {"id": -1, "file": s["file"]}
            src, slow, cx = s["start"], 1.0, s.get("cx", 0.5)
        else:
            c = clips[s["clip"]]
            ok_from, ok_to = stable_range(CLIPS / c["file"], c["start"], c["end"], (c["start"] + c["end"]) / 2)
            src = max(c["start"] + s.get("skip", 0.15), ok_from)
            have = min(c["end"], ok_to) - src - 0.04
            if "skip" not in s and have > need:
                ref = (c["start"] + c["end"]) / 2
                src = min(max(src, ref - need / 2), min(c["end"], ok_to) - 0.04 - need)
                have = min(c["end"], ok_to) - src - 0.04
            slow = max(1.0, need / have)
            if slow > 1.25:
                sys.exit(f"shot {i} (clip {c['id']}): {have:.2f} s of picture for {need:.2f} s of words")
            cx = s.get("cx", 0.5)
            info = next((v for k, v in sources.items() if c["file"].startswith(k)), {})
            if info.get("use") is False:
                sys.exit(f"shot {i} (clip {c['id']}): this file must not be used ({info.get('why')})")
            logo = c.get("logo") or info.get("logo")
            safe = {"right": min(cx, 0.61), "left": max(cx, 0.465), "both": min(max(cx, 0.465), 0.61)}.get(logo, cx)
            cx = safe
        graph = (f"[0:v]setpts={slow:.4f}*PTS,fps={FPS},split=2[a][b];"
                 f"[a]scale=-2:1920,crop=1080:1920:'min(max({cx}*iw-540,0),iw-1080)':0,gblur=sigma=30,"
                 f"eq=brightness=-0.07:saturation=0.9[bg];"
                 f"[b]crop='floor(ih*0.8/2)*2':ih:'min(max({cx}*iw-ih*0.4,0),iw-ih*0.8)':0,scale=1080:1350:flags=lanczos[fg];"
                 f"[bg][fg]overlay=0:{TOP},format=yuv420p[v]")
        out = parts / f"shot_{i:02d}.mp4"
        run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{src:.3f}", "-t", f"{need / slow + 0.2:.3f}",
             "-i", CLIPS / c["file"], "-an", "-filter_complex", graph, "-map", "[v]", "-frames:v", frames,
             "-r", FPS, "-c:v", "libx264", "-crf", "15", "-preset", "veryfast", out])
        listing.append(f"file '{out.as_posix()}'")
        print(f"shot {i:2d}  {begin:6.2f} s  clip {c['id']:3d}  {need:.2f} s" + (f"  slowed x{slow:.2f}" if slow > 1 else ""), flush=True)
    (parts / "list.txt").write_text("\n".join(listing) + "\n", encoding="utf-8")
    write_ass(json.loads((folder / "captions.json").read_text(encoding="utf-8")), folder / "captions_video.ass", offset=lead)

    brand = BRAND.exists() and edit.get("brand", True)
    inputs = ["-f", "concat", "-safe", "0", "-i", parts / "list.txt"]
    picture = f"[0:v]ass=captions_video.ass:fontsdir='{FONTS}'[v]"
    if brand:
        inputs += ["-loop", "1", "-framerate", FPS, "-t", total, "-i", BRAND]
        picture = ("[1:v]format=rgba,fade=t=in:st=0:d=0.35:alpha=1[brand];"
                   f"[0:v][brand]overlay=0:0:format=auto,ass=captions_video.ass:fontsdir='{FONTS}'[v]")
    vi = 2 if brand else 1                                              # index of the voice input
    inputs += ["-i", voice]
    v_gain = VOICE_LUFS - lufs(voice)
    audio = f"[{vi}:a]aresample=48000,volume={v_gain:.2f}dB,adelay=delays={int(lead * 1000)}:all=1,apad[voice];"
    music, start = edit.get("music"), edit.get("music_start", 0)
    if music:
        m_gain = VOICE_LUFS - MUSIC_UNDER - lufs(music, start, total)
        inputs += ["-ss", start, "-i", music]
        audio += (f"[{vi + 1}:a]aresample=48000,volume={m_gain:.2f}dB,afade=t=in:d=0.4,"
                  f"afade=t=out:st={total - 1.6:.2f}:d=1.6[m];"
                  f"[voice][m]amix=inputs=2:duration=longest:normalize=0,alimiter=limit=0.84:level=false[a]")
    else:
        audio += "[voice]alimiter=limit=0.84:level=false[a]"
    video = folder / "video.mp4"
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *inputs, "-filter_complex", f"{picture};{audio}",
         "-map", "[v]", "-map", "[a]", "-t", total, "-r", FPS,
         "-c:v", "libx264", "-crf", "19", "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
         "-ar", "48000", "-ac", "2", "-movflags", "+faststart", video], cwd=folder)

    # --- checks -------------------------------------------------------------------------------------------------
    check = folder / "check"
    check.mkdir(exist_ok=True)
    font = ImageFont.truetype(str(FONTS / "OpenSans-Bold.ttf"), 26)
    cols = 8
    rows = -(-len(shots) // cols)
    sheet = Image.new("RGB", (cols * 270, rows * 510), "black")
    draw = ImageDraw.Draw(sheet)
    for i, s in enumerate(shots):
        begin = 0.0 if i == 0 else round((lead + s["t"]) * FPS) / FPS
        end = round((lead + shots[i + 1]["t"]) * FPS) / FPS if i + 1 < len(shots) else total
        frame = check / f"shot_{i:02d}.jpg"
        run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{(begin + end) / 2:.2f}", "-i", video,
             "-frames:v", "1", "-vf", "scale=270:480", frame])
        x, y = (i % cols) * 270, (i // cols) * 510
        sheet.paste(Image.open(frame), (x, y + 30))
        draw.text((x + 6, y + 1), f"{i}  {begin:.1f}s", fill="yellow", font=font)
    sheet.save(check / "sheet.jpg", quality=88)
    info = {"seconds": round(seconds(video), 2), "lead_s": lead, "shots": len(shots), "loudness_lufs": lufs(video),
            "voice_gain_db": round(v_gain, 1), "music_under_voice_db": MUSIC_UNDER if music else None,
            "brand": bool(brand), "size_mb": round(video.stat().st_size / 2**20, 1)}
    (check / "info.json").write_text(json.dumps(info, indent=1), encoding="utf-8")
    print(json.dumps(info))


if __name__ == "__main__":
    main(sys.argv[1])

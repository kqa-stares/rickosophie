"""Check new scripts and add them to topics.json. Refuses anything outside the rules.

  python3 src/add_content.py content/batch02.json

A content file is a JSON list of topics:
{"id": "lundi-matin",                                  lowercase words with dashes, never used before
 "title": {"fr": "Le lundi matin"},                     short, for Telegram messages
 "lines": {"fr": ["bloc 1", ..., "bloc 6"]},            EXACTLY 6 blocks, each 30 to 50 words, 225 to 255 words in all
 "images": ["English descriptions | of pictures | for block 1", ... 6 lines],
 "caption": "One French sentence for the post, 6 to 25 words.",
 "hashtags": "#four #lowercase #topic #tags"}
Script rules (docs/personnage-rick.md): spoken French for a voice, numbers in letters, no digits, no symbols other
than . , ? ! : ' -, no quotes or parentheses, never "Morty", at most two swear words, and the last block asks the
viewer a question.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SWEAR = ("putain", "merde", "bordel", "connard", "connards", "enculé", "salope", "pute")
BANNED = ("morty", "wubba", "lubba", "adult swim")


def words(text):
    return [w for w in text.split() if re.search(r"\w", w)]


def problems(t, known_ids, known_lines):
    p = []
    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", t.get("id", "")):
        p.append("id must be lowercase words with dashes")
    if t.get("id") in known_ids:
        p.append("id already used")
    lines = t.get("lines", {}).get("fr", [])
    if len(lines) != 6:
        p.append(f"{len(lines)} blocks instead of 6")
    counts = [len(words(l)) for l in lines]
    if any(not 30 <= c <= 50 for c in counts):
        p.append(f"block lengths {counts} (30 to 50 words each)")
    if not 225 <= sum(counts) <= 255:
        p.append(f"{sum(counts)} words in all (225 to 255)")
    text = " ".join(lines)
    low = text.lower()
    if re.search(r"\d", text):
        p.append("digits in the script (write numbers in letters)")
    if re.search(r"[\"«»()\[\]{}%€$&*#@/<>_=+]", text):
        p.append("symbols, quotes or parentheses in the script")
    if any(b in low for b in BANNED):
        p.append("a word from the series that must not be said (Morty, catchphrases)")
    n_swear = sum(len(re.findall(rf"\b{s}\b", low)) for s in SWEAR)
    if n_swear > 2:
        p.append(f"{n_swear} swear words (2 at most)")
    if lines and "?" not in lines[-1]:
        p.append("the last block must ask the viewer a question")
    for l in lines:
        for sentence in re.split(r"(?<=[.?!])\s+", l):
            if len(words(sentence)) >= 6 and sentence.strip().lower() in known_lines:
                p.append(f"sentence already used in another script: {sentence[:60]}")
    images = t.get("images", [])
    if len(images) != len(lines) or any(len([h for h in i.split("|") if h.strip()]) < 2 for i in images):
        p.append("images: one line per block, at least 2 descriptions separated by |")
    if any(re.search(r"[àâçéèêëîïôûùœ]", i) for i in images):
        p.append("images must be written in English")
    if not 6 <= len(words(t.get("caption", ""))) <= 25:
        p.append("caption: 6 to 25 words")
    tags = t.get("hashtags", "").split()
    if len(tags) != 4 or any(not re.fullmatch(r"#[a-z0-9]+", h) for h in tags) or "#rickosophie" in tags:
        p.append("hashtags: exactly 4 lowercase tags, not #rickosophie (added automatically)")
    if not t.get("title", {}).get("fr"):
        p.append("title missing")
    return p


def main(path):
    topics_file = ROOT / "topics.json"
    topics = json.loads(topics_file.read_text(encoding="utf-8")) if topics_file.exists() else []
    known_ids = {t["id"] for t in topics}
    known_lines = {s.strip().lower() for t in topics for l in t["lines"]["fr"] for s in re.split(r"(?<=[.?!])\s+", l)
                   if len(words(s)) >= 6}
    new = json.loads(Path(path).read_text(encoding="utf-8"))
    bad = 0
    for t in new:
        p = problems(t, known_ids, known_lines)
        if p:
            bad += 1
            print(f"REFUSED {t.get('id')}: " + "; ".join(p))
        known_ids.add(t.get("id"))
    if bad:
        sys.exit(f"{bad} of {len(new)} topics refused: fix them and run again (nothing was added).")
    topics += new
    topics_file.write_text(json.dumps(topics, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(new)} topics added, {len(topics)} in topics.json")


if __name__ == "__main__":
    main(sys.argv[1])

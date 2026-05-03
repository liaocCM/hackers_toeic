"""Parse bilingual Whisper transcripts (transcripts/1-basic/dayXX.json) into a
structured vocab dataset (data/1-basic/dayXX.json).

The audio format is: English word (×N) followed by its Traditional-Chinese
gloss(es), repeated for each entry. Whisper output is noisy — Chinese is
sometimes missing, sometimes fused without spaces, sometimes mixed with
pinyin renderings. This parser is best-effort and English vocabulary is the
precise output; Chinese glosses should be calibrated against the source.
"""

from __future__ import annotations
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "transcripts" / "1-basic"
DST_DIR = ROOT / "data" / "1-basic"
THEMES = json.loads((ROOT / "themes.json").read_text())

CJK_RE = re.compile(r"[一-鿿]")
HEADER_WORDS = {
    "hackers", "hacker", "toeic", "toic", "stoic",
    "vocabulary", "vocab", "day",
}


def is_cjk(c: str) -> bool:
    return bool(CJK_RE.match(c))


def is_en_letter(c: str) -> bool:
    return c.isascii() and c.isalpha()


def tokenize(text: str) -> list[tuple[str, str]]:
    """Split text into (kind, content) segments where kind is 'en' or 'zh'."""
    segs: list[tuple[str, str]] = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if is_cjk(c):
            j = i
            while j < n and (is_cjk(text[j]) or text[j] in "、，,"):
                j += 1
            segs.append(("zh", text[i:j]))
            i = j
        elif c.isascii() and (c.isalpha() or c == "'"):
            j = i
            # Allow internal whitespace, hyphens and apostrophes as part of an English run
            while j < n:
                ch = text[j]
                if ch.isascii() and (ch.isalpha() or ch in " -'"):
                    j += 1
                elif ch == ",":
                    j += 1
                else:
                    break
            segs.append(("en", text[i:j]))
            i = j
        else:
            i += 1
    return segs


def clean_gloss(s: str) -> list[str]:
    """Split Chinese gloss into a list of senses; drop empties/dupes."""
    s = s.strip(" ,.、，。;；:：")
    parts = re.split(r"[、,，;；]", s)
    out: list[str] = []
    seen: set[str] = set()
    for p in parts:
        p = p.strip(" .，。、")
        if p and p not in seen:
            out.append(p)
            seen.add(p)
    return out


def split_en_run(s: str) -> list[str]:
    """Split an English-text run into individual word entries.
    e.g. "respond, infuriate, courteous" -> ["respond", "infuriate", "courteous"]
    Multi-word phrases like "fill in" stay as one entry.
    """
    pieces = re.split(r"[,]+", s)
    out: list[str] = []
    for p in pieces:
        w = p.strip(" .'-").lower()
        if not w:
            continue
        # collapse multiple spaces
        w = re.sub(r"\s+", " ", w)
        out.append(w)
    return out


def parse_text(text: str) -> list[dict]:
    """Walk text -> ordered list of {word, meaning_zh} dicts."""
    # Strip leading header up through "Day N"
    m = re.search(r"(?i)day\s*\d+\.?", text)
    if m:
        text = text[m.end():]

    pairs: list[dict] = []
    pending: list[str] = []
    seen_words: set[str] = set()

    def push(word: str, gloss: str = "") -> None:
        word = word.strip(" .'-").lower()
        if not word or word in HEADER_WORDS:
            return
        # Drop pure numerics
        if word.isdigit():
            return
        # Dedupe within day (keep first occurrence's order)
        key = word
        if key in seen_words:
            return
        seen_words.add(key)
        pairs.append({
            "word": word,
            "meaning_zh": clean_gloss(gloss),
        })

    for kind, content in tokenize(text):
        if kind == "en":
            words = split_en_run(content)
            # Collapse consecutive duplicates (whisper echo: "Confidence Confidence")
            for w in words:
                if pending and pending[-1] == w:
                    continue
                pending.append(w)
        else:  # zh
            if pending:
                for w in pending[:-1]:
                    push(w, "")
                push(pending[-1], content)
                pending = []

    # Flush trailing words with no gloss
    for w in pending:
        push(w, "")

    return pairs


def main() -> None:
    DST_DIR.mkdir(parents=True, exist_ok=True)
    days_meta = {d["day"]: d for d in THEMES["days"]}

    summary = []
    all_data = []
    for src in sorted(SRC_DIR.glob("day*.json")):
        day_num = int(re.search(r"day(\d+)", src.stem).group(1))
        raw = json.loads(src.read_text())
        text = raw.get("text", "")
        vocab = parse_text(text)
        meta = days_meta.get(day_num, {})

        record = {
            "day": day_num,
            "theme": meta.get("theme"),
            "category": meta.get("category"),
            "page": meta.get("page"),
            "audio_source": f"audio/1-basic_Day01-30/basic_Day{day_num:02d}.mp3",
            "transcript_model": "Systran/faster-whisper-medium",
            "low_count_warning": len(vocab) < 25,
            "raw_transcript": text,
            "vocab": vocab,
        }

        out = DST_DIR / f"day{day_num:02d}.json"
        out.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
        all_data.append(record)
        summary.append((day_num, len(vocab), sum(1 for v in vocab if v["meaning_zh"])))

    (DST_DIR / "all.json").write_text(
        json.dumps({"days": all_data}, ensure_ascii=False, indent=2) + "\n"
    )

    print(f"{'day':>4} {'words':>6} {'with_gloss':>11}")
    for d, w, g in summary:
        print(f"{d:>4} {w:>6} {g:>11}")
    total_words = sum(w for _, w, _ in summary)
    total_gloss = sum(g for _, _, g in summary)
    print(f"\ntotal: {total_words} words, {total_gloss} with gloss "
          f"({100*total_gloss/total_words:.0f}%)")


if __name__ == "__main__":
    main()

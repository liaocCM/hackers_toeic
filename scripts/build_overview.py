"""Generate OVERVIEW.md from data/1-basic/all.json — index + per-day vocab tables."""

from __future__ import annotations
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "1-basic" / "all.json"
DST = ROOT / "BASIC_OVERVIEW.md"


def main() -> None:
    data = json.loads(SRC.read_text())
    days = data["days"]

    total_words = sum(len(d.get("vocab", [])) for d in days)
    total_gloss = sum(
        sum(1 for v in d.get("vocab", []) if v["meaning_zh"]) for d in days
    )
    models = sorted({d.get("transcript_model") for d in days if d.get("transcript_model")})

    lines: list[str] = []
    lines.append("# TOEIC Vocabulary — 30 Day Overview\n")
    lines.append(f"Total days: {len(days)}  ")
    pct = 100 * total_gloss / total_words if total_words else 0
    lines.append(f"Total words: {total_words} ({total_gloss} with gloss, {pct:.0f}%)")
    lines.append(f"Transcript model: {', '.join(models)}\n")

    lines.append("## Index\n")
    lines.append("| Day | Theme | Category | Words |")
    lines.append("|---|---|---|---|")
    for d in days:
        warn = " ⚠️" if d.get("low_count_warning") else ""
        anchor = f"day-{d['day']}--{d.get('theme','')}"
        lines.append(
            f"| [Day {d['day']}](#{anchor}) | {d.get('theme','')} | "
            f"{d.get('category','')} | {len(d.get('vocab', []))}{warn} |"
        )
    lines.append("")

    for d in days:
        vocab = d.get("vocab", [])
        lines.append(f"## Day {d['day']} — {d.get('theme','')}")
        meta = (
            f"**Category:** {d.get('category','')}　"
            f"**Page:** {d.get('page','')}　"
            f"**Words:** {len(vocab)}"
        )
        if d.get("low_count_warning"):
            meta += "　⚠️ low count"
        lines.append(meta + "\n")
        lines.append("| # | Word | 中文 |")
        lines.append("|---|---|---|")
        for i, v in enumerate(vocab, 1):
            meaning = " / ".join(v.get("meaning_zh", []))
            lines.append(f"| {i} | {v.get('word','')} | {meaning} |")
        lines.append("")

    DST.write_text("\n".join(lines))
    print(f"wrote {DST.relative_to(ROOT)} ({DST.stat().st_size} bytes, {len(lines)} lines)")


if __name__ == "__main__":
    main()

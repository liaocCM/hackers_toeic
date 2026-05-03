# Hackers TOEIC Vocabulary

Structured vocabulary dataset extracted from the *Hacker's TOEIC Vocabulary* audio collection (30 days × ~30 words/day). English vocabulary is the precise output; Traditional-Chinese glosses are best-effort and flagged for calibration.

## Layout

```
themes.json                 day -> theme/category/page mapping
design.md                   collection notes
audio/                      source mp3s (gitignored — copyrighted)
  1-basic_Day01-30/         word + Chinese gloss (US accent)
  2-all_Day01-30/           word + 2 example sentences each
  3-score-basic_Day01-30/   score-tier basic, LC/RC split
  4-score-800_Day01-30/     score-tier 800+, LC/RC split
  5-score-900_Day01-30/     score-tier 900+, LC/RC split
  6-phrase120/              120 idiomatic phrases
transcripts/                raw Whisper output (verbose_json)
  1-basic/                  bilingual: faster-whisper-medium + initial_prompt + opencc s2tw
  1-basic-en/               English-only: faster-whisper-medium.en (cross-reference)
data/                       parsed dataset
  1-basic/dayXX.json        per-day vocab list
  1-basic/all.json          merged
scripts/
  parse_vocab.py            transcripts -> data parser
```

## Per-day record schema

```json
{
  "day": 1,
  "theme": "應徵失業",
  "category": "雇用",
  "page": 22,
  "audio_source": "audio/1-basic_Day01-30/basic_Day01.mp3",
  "transcript_model": "Systran/faster-whisper-medium",
  "low_count_warning": false,
  "raw_transcript": "...",
  "vocab": [
    { "word": "resume", "meaning_zh": ["履歷表"], "verified": false }
  ]
}
```

- `low_count_warning: true` — fewer than 25 entries parsed; raw transcript was incomplete (likely days 8, 11, 26, 29). Manual augmentation needed.
- `verified: false` — Chinese meaning came from Whisper ASR; flip to `true` after proofreading.

## Reproducing the transcripts

ASR server: [speaches](https://github.com/speaches-ai/speaches), `Systran/faster-whisper-medium` (multilingual, with bilingual `initial_prompt`) + `Systran/faster-whisper-medium.en` (English-only cross-reference). Output is converted Simplified→Traditional via `opencc -c s2tw`.

Server config that matters:
```
WHISPER__NUM_WORKERS=3
STT_MODEL_TTL=3600
```

## Status

- **Folder 1 (basic, word + Chinese gloss)**: parsed into `data/1-basic/`. ~1060 vocab entries across 30 days.
- **Folders 2–6**: not yet processed. Folder 2 (`2-all`, with example sentences) is next.

## Known issues in the ASR pipeline

- Whisper picks one language per file when audio is mixed CN+EN, dropping content in the other. Mitigated by passing a bilingual `initial_prompt` — works on ~24/30 days; the rest get partial coverage and a `low_count_warning`.
- Start-of-audio loop hallucinations (e.g. day 14 "第14" repeated 60+ times) are a separate failure mode the prompt does not fix. The English-only model (`medium.en`) is unaffected by this loop but renders Chinese as pinyin on some days.
- Tail repetition loops occur intermittently. The parser deduplicates consecutive repeated words but does not strip mid-content loops.

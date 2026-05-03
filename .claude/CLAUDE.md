# Hackers TOEIC Vocabulary Dataset

Structured vocab dataset extracted from the *Hacker's TOEIC Vocabulary* audio collection. English vocabulary is the precise output; Traditional-Chinese glosses are best-effort and flagged for calibration.

## Repo layout

- `audio/` — source mp3s, **gitignored** (~648 MB, copyrighted)
  - `1-basic_Day01-30/` — word + Chinese gloss
  - `2-all_Day01-30/` — word + 2 example sentences
  - `3-score-basic_Day01-30/`, `4-score-800_*`, `5-score-900_*` — LC/RC split tiers
  - `6-phrase120/` — 120 idiomatic phrases (no day index)
- `transcripts/` — raw Whisper output (`verbose_json`)
  - `1-basic/dayXX.json` — bilingual (`medium` + bilingual `initial_prompt` + `opencc s2tw`)
  - `1-basic-en/dayXX.json` — English-only (`medium.en`) cross-reference
- `data/1-basic/dayXX.json` — parsed dataset (per-day vocab list)
- `data/1-basic/all.json` — merged
- `scripts/parse_vocab.py` — transcripts → data parser
- `themes.json` — day → theme/category/page mapping
- `design.md` — collection notes

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
    { "word": "resume", "meaning_zh": ["履歷表"] }
  ]
}
```

- English vocab is precise; Chinese glosses came from ASR and need calibration against the source.
- `low_count_warning: true` — parser yielded < 25 entries. Days 8, 11, 26, 29 need manual augmentation against `transcripts/1-basic-en/` (which has different/complementary noise).

## Status

| Folder | State | Notes |
|---|---|---|
| `1-basic` | ✅ extracted | ~1060 entries, 30 days, in `data/1-basic/` |
| `2-all` | ⏳ next | Has example sentences; mid-content loops are a known risk |
| `3-score-basic` | not started | LC/RC split format |
| `4-score-800` | not started | LC/RC split |
| `5-score-900` | not started | LC/RC split |
| `6-phrase120` | not started | 120 phrases, no day index |

## ASR pipeline (what works, what doesn't)

**Server**: [speaches](https://github.com/speaches-ai/speaches) at `http://192.168.1.109:8000` (LAN). 16 GB VRAM. OpenAI-compatible `/v1/audio/transcriptions`.

**Server config that matters** (set via env vars on the docker container):
```
WHISPER__NUM_WORKERS=3      # true GPU parallelism, ~25% throughput gain
STT_MODEL_TTL=3600          # keep model resident during batch jobs
```
Persist `~/.cache/huggingface` via volume mount or downloaded models vanish on restart.

**Model choices** (validated empirically):
- `Systran/faster-whisper-medium` is the practical default. `small` has catastrophic loop hallucinations on drilled vocab audio. `large-v3` is 2.4× slower, regresses Traditional → Simplified, and **moves loops from tail to mid-content** (worse, not better).
- `Systran/faster-whisper-medium.en` — English-only. Strictly more accurate on pure English, immune to Chinese-token loops. Use when Chinese isn't needed, or as cross-reference. Sometimes renders Chinese audio as pinyin garbage.
- `Systran/faster-distil-whisper-*` are English-only. **Do not use** when Chinese must be transcribed.

**Critical gotchas**:
- `language=en` actively suppresses Chinese on some files. Auto-detect (no language flag) is more reliable for mixed CN+EN audio.
- A bilingual `initial_prompt` showing the expected `English 中文` pattern dramatically improves coverage on otherwise-broken days. The current prompt lives in the rerun command (see `scripts/`).
- Whisper output is Simplified Chinese; convert with `opencc -c s2tw` for Traditional. The converter is mature and essentially loss-free for this content.

**Optimal client concurrency**: 6 (with `num_workers=3`). Beyond ~6 just queues.

## User preferences (validated)

- Traditional Chinese is required (source is a Korean/Taiwan publication).
- For mixed-language audio extraction: precision target is the **English** word list. Chinese glosses can be best-effort with `verified: false`; user calibrates afterwards.
- Folder names use the format `N-name_DayXX-YY` (number, hyphen, name; underscores within name parts).

## Common commands

```bash
# Re-transcribe one folder (edit folder + model as needed)
D="audio/1-basic_Day01-30"
PROMPT="Hackers TOEIC vocabulary list. resume 履歷表, opening 空缺、職缺、開張, applicant 申請者、應徵者, requirement 必要條件, qualified 有資格的, candidate 候選者, confidence 信心、自信, professional 專業的、職業的, achievement 成就、達成."
for i in $(seq -w 01 30); do
  ( curl -s -X POST http://192.168.1.109:8000/v1/audio/transcriptions \
      -F "file=@$D/basic_Day$i.mp3" \
      -F "model=Systran/faster-whisper-medium" \
      -F "response_format=verbose_json" \
      -F "prompt=$PROMPT" \
      > "transcripts/1-basic/day$i.json" ) &
  if (( $(jobs -r | wc -l) >= 6 )); then wait -n; fi
done
wait

# Convert Simplified -> Traditional in-place
python3 -c "
import json, subprocess, pathlib
for f in sorted(pathlib.Path('transcripts/1-basic').glob('day*.json')):
    d = json.loads(f.read_text())
    conv = lambda s: subprocess.run(['opencc','-c','s2tw'], input=s, capture_output=True, text=True, check=True).stdout.rstrip('\n') if s else s
    d['text'] = conv(d['text'])
    for seg in d.get('segments', []):
        if 'text' in seg: seg['text'] = conv(seg['text'])
    f.write_text(json.dumps(d, ensure_ascii=False, indent=2))
"

# Re-parse to data/
python3 scripts/parse_vocab.py
```

## Don't do

- Don't push the `audio/` folder. It's copyrighted and large.
- Don't pass `language=en` to Whisper for the bilingual collection — it suppresses Chinese unpredictably.
- Don't trust ASR output as final. Even the "good" days have homonym errors (meet → meat) and 1–2 char Chinese typos. Plan for manual proofread before publishing.

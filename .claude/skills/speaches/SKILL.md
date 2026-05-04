---
name: speaches
description: Transcribe audio (and synthesize speech) via a self-hosted speaches server (https://github.com/speaches-ai/speaches), which exposes OpenAI-compatible /v1/audio endpoints. Use when extracting English/Chinese (or any of 99 other languages) text from mp3/wav/m4a/etc. Handles single files, batch directories with concurrency, bilingual-prompt nudging for mixed CN+EN audio, and optional opencc s2tw post-processing for traditional Chinese output.
---

# Speaches integration skill

Transcribe audio against a self-hosted [speaches](https://github.com/speaches-ai/speaches) server. The endpoints are OpenAI-compatible (`/v1/audio/transcriptions`, `/v1/audio/speech`), so the same scripts work against `api.openai.com` if you point `--base-url` there.

## When to use

- User has audio files to transcribe and the project references this skill or a speaches server.
- User asks "transcribe with speaches", "use my speaches server", or "kick off batch transcription against my host".
- User wants to TTS some text using a Kokoro voice.

## Required configuration

You **must** set the server URL before any transcribe/TTS call. Resolution order:

1. CLI flag `--base-url`
2. Env var `SPEACHES_BASE_URL`
3. `~/.claude/skills/speaches/config/settings.yaml` (gitignored)

Optional auth (only needed if your server has `API_KEY` set):

1. CLI flag `--api-key`
2. Env var `SPEACHES_API_KEY`
3. `~/.claude/skills/speaches/config/settings.yaml`

Example:

```yaml
# config/settings.yaml  (this file is gitignored — your URL/key never leak)
base_url: "https://your-speaches-host.example.com"
api_key: ""    # leave empty if your server has no auth
```

## Quick start

```bash
SKILL=~/.claude/skills/speaches
export SPEACHES_BASE_URL=https://your-speaches-host.example.com

# Single file → JSON transcript
python3 $SKILL/scripts/transcribe.py audio.mp3 -o transcript.json

# Batch a directory → one JSON per audio file
python3 $SKILL/scripts/transcribe.py --dir audio/1-basic/ --output-dir transcripts/1-basic/ --concurrency 6

# Bilingual audio (CN + EN) — opt-in safe prompt + auto convert to traditional
python3 $SKILL/scripts/transcribe.py --dir audio/ --output-dir transcripts/ --bilingual-prompt --convert s2tw

# List models on the configured server
python3 $SKILL/scripts/transcribe.py --list-models
```

## Common models on a typical speaches deployment

| Model | Languages | Notes |
|---|---|---|
| `Systran/faster-whisper-medium` (default) | 99 | Practical default. Robust on mixed CN+EN. |
| `Systran/faster-whisper-medium.en` | en | English-only. Strictly more accurate on pure English. |
| `Systran/faster-whisper-small` | 99 | Faster but has catastrophic loop hallucinations on drilled vocab audio — **do not use** for repetitive content. |
| `speaches-ai/Kokoro-82M-v1.0-ONNX-int8` | multilingual | TTS, ~50 voices. Used by `tts.py`. |

Run `transcribe.py --list-models` to fetch the live list from your server.

## Critical gotchas (validated empirically)

1. **Don't pass `language=en` for mixed audio** — it actively suppresses Chinese on some files. Auto-detect (no `--language` flag) is more reliable for CN+EN.
2. **Bilingual prompt examples must NOT collide with actual vocab in the audio.** Whisper treats `prompt` as text it has already transcribed and skips matching audio segments. Use generic everyday words (apple/banana/computer/desk/...). The `--bilingual-prompt` flag uses a validated safe default.
3. **Whisper output is Simplified Chinese.** Use `--convert s2tw` (requires `opencc` CLI: `brew install opencc`) to convert. The conversion is mature and essentially loss-free for vocab content.
4. **Optimal client concurrency: 6.** Beyond ~6 just queues against the server.
5. `large-v3` (when available) regresses Traditional → Simplified and moves loops from tail to mid-content. `medium` is the right default.
6. **Hostnames containing `_` will fail TLS verification** in Python's `ssl` module (RFC 1123) even when the cert legitimately covers them via wildcard SAN. The scripts auto-detect underscore hostnames and disable TLS verification with a one-line warning. Pass `--insecure` to do the same explicitly for any host.

## Script reference

### `scripts/transcribe.py`

| Flag | Description |
|---|---|
| `files` | Positional: one or more audio files |
| `--dir DIR` | Batch all audio files in a directory (mp3/wav/m4a/flac/ogg) |
| `--output, -o FILE` | Output JSON path (single file mode) |
| `--output-dir DIR` | Output directory (batch mode); writes `<stem>.json` per input |
| `--model MODEL` | Default `Systran/faster-whisper-medium` |
| `--language LANG` | Force a language code. Omit for auto-detect (recommended for mixed audio) |
| `--prompt TEXT` | Free-form prompt; nudges format/spelling. See gotcha #2 |
| `--bilingual-prompt` | Use a validated safe bilingual prompt (apple 蘋果, banana 香蕉, ...) |
| `--response-format` | `verbose_json` (default), `json`, `text`, `srt`, `vtt` |
| `--convert s2tw` | Post-process Chinese text via `opencc -c s2tw` (Simplified → Traditional) |
| `--concurrency N` | Parallel uploads (batch mode only); default 6 |
| `--base-url URL` | Required (or via env / settings.yaml). |
| `--api-key KEY` | Bearer token (only if the server requires it) |
| `--insecure` | Disable TLS verification (also auto-disabled for hostnames containing `_`) |
| `--list-models` | Print models on the server and exit |

### `scripts/tts.py`

| Flag | Description |
|---|---|
| `--text TEXT` | Text to synthesize (required unless `--list-voices`) |
| `--file FILE` | Read text from a file instead |
| `--voice NAME` | Default `af_heart`. Use `--list-voices` to enumerate |
| `--output, -o FILE` | Output audio file (default: `tts.mp3`) |
| `--format` | `mp3` (default), `wav`, `flac`, `pcm`, `opus`, `aac` |
| `--speed` | 0.25 to 4.0 (default 1.0) |
| `--base-url URL` | Required (or via env / settings.yaml) |
| `--api-key KEY` | Bearer token (only if the server requires it) |
| `--insecure` | Disable TLS verification |
| `--list-voices` | Print available voices and exit |

## Common patterns

**Re-transcribe a folder of TOEIC-style drilled vocab audio (mixed CN+EN):**

```bash
SKILL=~/.claude/skills/speaches
export SPEACHES_BASE_URL=https://your-speaches-host.example.com
python3 $SKILL/scripts/transcribe.py \
  --dir audio/1-basic_Day01-30/ \
  --output-dir transcripts/1-basic/ \
  --bilingual-prompt \
  --convert s2tw \
  --concurrency 6
```

**Cross-check with English-only model as a second source:**

```bash
python3 $SKILL/scripts/transcribe.py \
  --dir audio/1-basic_Day01-30/ \
  --output-dir transcripts/1-basic-en/ \
  --model Systran/faster-whisper-medium.en
```

**TTS a vocab review prompt:**

```bash
python3 $SKILL/scripts/tts.py \
  --text "Today's vocabulary review: resume, opening, applicant." \
  --voice af_bella \
  --output review.mp3
```

## Publishing this skill

If you publish this skill repo:

- `config/settings.yaml` is **gitignored**. Ship `config/settings.example.yaml` instead.
- The scripts have **no hard-coded host**. Anyone using the skill must set `SPEACHES_BASE_URL` for themselves.
- If your server is reachable from the public internet, set `API_KEY` on the speaches container so a leaked URL isn't a free-compute disclosure.

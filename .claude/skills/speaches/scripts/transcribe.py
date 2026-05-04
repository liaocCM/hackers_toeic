#!/usr/bin/env python3
"""Transcribe audio via a speaches server (OpenAI-compatible /v1/audio/transcriptions).

Single file:
  transcribe.py audio.mp3 -o transcript.json

Batch a directory (writes one JSON per audio, mirroring filenames):
  transcribe.py --dir audio/ --output-dir transcripts/ --concurrency 6

Bilingual audio (e.g. CN+EN drill):
  transcribe.py --dir audio/ --output-dir transcripts/ --bilingual-prompt --convert s2tw
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
import urllib3
import yaml


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
DEFAULT_MODEL = "Systran/faster-whisper-medium"
AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".webm", ".mp4"}

# Validated safe bilingual prompt — uses generic everyday words so they don't
# collide with any actual vocab in the audio (which would cause Whisper to skip
# matching segments).
BILINGUAL_PROMPT = (
    "Bilingual word list with Traditional Chinese definitions. "
    "apple 蘋果, banana 香蕉, computer 電腦, desk 書桌, "
    "elephant 大象, flower 花朵."
)


def load_config() -> dict:
    cfg = {
        "base_url": os.getenv("SPEACHES_BASE_URL", ""),
        "api_key": os.getenv("SPEACHES_API_KEY", ""),
    }
    yaml_path = SKILL_DIR / "config" / "settings.yaml"
    if yaml_path.exists():
        try:
            data = yaml.safe_load(yaml_path.read_text()) or {}
            if not cfg["base_url"] and data.get("base_url"):
                cfg["base_url"] = data["base_url"]
            if not cfg["api_key"] and data.get("api_key"):
                cfg["api_key"] = data["api_key"]
        except Exception as e:
            print(f"[warn] could not parse {yaml_path}: {e}", file=sys.stderr)
    return cfg


def auth_headers(api_key: str) -> dict:
    return {"Authorization": f"Bearer {api_key}"} if api_key else {}


_warned_insecure = False


def resolve_verify(base_url: str, insecure: bool) -> bool:
    """Return the requests `verify` value; auto-disable for underscore hostnames.

    Hostnames containing '_' aren't valid DNS labels (RFC 1123) so Python's
    ssl module refuses to match them against the certificate, even when the
    server's wildcard cert legitimately covers them. We auto-disable and warn
    once.
    """
    global _warned_insecure
    if insecure:
        if not _warned_insecure:
            print("[warn] TLS verification disabled (--insecure)", file=sys.stderr)
            _warned_insecure = True
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        return False
    host = urlparse(base_url).hostname or ""
    if "_" in host:
        if not _warned_insecure:
            print(
                f"[warn] '{host}' contains '_' which Python's ssl module rejects; "
                "auto-disabling TLS verification.",
                file=sys.stderr,
            )
            _warned_insecure = True
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        return False
    return True


def list_models(base_url: str, api_key: str, verify: bool) -> int:
    resp = requests.get(
        f"{base_url.rstrip('/')}/v1/models",
        headers=auth_headers(api_key),
        timeout=20,
        verify=verify,
    )
    resp.raise_for_status()
    data = resp.json().get("data", [])
    print(f"{len(data)} model(s) on {base_url}\n")
    for m in data:
        task = m.get("task", "")
        langs = m.get("language", [])
        lang_str = (
            f"{len(langs)} langs"
            if isinstance(langs, list) and len(langs) > 5
            else json.dumps(langs, ensure_ascii=False)
        )
        print(f"  {m['id']:60s} {task:30s} {lang_str}")
    return 0


def opencc_convert(text: str, profile: str) -> str:
    if not text:
        return text
    if not shutil.which("opencc"):
        raise RuntimeError(
            "opencc CLI not found. Install with: brew install opencc"
        )
    proc = subprocess.run(
        ["opencc", "-c", profile],
        input=text,
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout.rstrip("\n")


def transcribe_file(
    path: Path,
    *,
    base_url: str,
    api_key: str,
    model: str,
    language: str | None,
    prompt: str | None,
    response_format: str,
    convert: str | None,
    timeout: float,
    verify: bool,
) -> dict:
    url = f"{base_url.rstrip('/')}/v1/audio/transcriptions"
    headers = auth_headers(api_key)

    with path.open("rb") as fh:
        files = {"file": (path.name, fh, "application/octet-stream")}
        data = {"model": model, "response_format": response_format}
        if language:
            data["language"] = language
        if prompt:
            data["prompt"] = prompt
        resp = requests.post(url, headers=headers, files=files, data=data,
                             timeout=timeout, verify=verify)

    if resp.status_code >= 300:
        raise RuntimeError(f"HTTP {resp.status_code} for {path.name}: {resp.text[:400]}")

    if response_format in ("json", "verbose_json"):
        result = resp.json()
    else:
        result = {"text": resp.text}

    # Annotate with what we used so the transcript file is self-describing.
    result.setdefault("transcript_model", model)

    if convert:
        if "text" in result:
            result["text"] = opencc_convert(result["text"], convert)
        for seg in result.get("segments", []):
            if "text" in seg:
                seg["text"] = opencc_convert(seg["text"], convert)

    return result


def gather_audio(paths: list[str], dir_arg: str | None) -> list[Path]:
    files: list[Path] = []
    if dir_arg:
        d = Path(dir_arg)
        if not d.is_dir():
            raise SystemExit(f"--dir {d} is not a directory")
        files.extend(
            sorted(p for p in d.iterdir() if p.is_file() and p.suffix.lower() in AUDIO_EXTS)
        )
    files.extend(Path(p) for p in paths)
    return files


def output_path_for(src: Path, output_dir: Path) -> Path:
    return output_dir / (src.stem + ".json")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Transcribe audio against a speaches server.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("files", nargs="*", help="Audio files to transcribe")
    parser.add_argument("--dir", help="Batch all audio files in a directory")
    parser.add_argument("--output", "-o", help="Output JSON path (single file mode)")
    parser.add_argument("--output-dir", help="Output directory (batch mode)")
    parser.add_argument("--model", default=DEFAULT_MODEL,
                        help=f"Model id (default: {DEFAULT_MODEL})")
    parser.add_argument("--language",
                        help="Language code (e.g. en, zh). Omit for auto-detect — recommended for mixed audio.")
    parser.add_argument("--prompt", help="Free-form prompt; nudges format/spelling.")
    parser.add_argument("--bilingual-prompt", action="store_true",
                        help="Use a validated safe bilingual prompt for CN+EN drill audio.")
    parser.add_argument("--response-format", default="verbose_json",
                        choices=["verbose_json", "json", "text", "srt", "vtt"])
    parser.add_argument("--convert", choices=["s2tw", "s2t", "t2s", "tw2s"],
                        help="Run opencc on transcribed text. s2tw = Simplified→Traditional (Taiwan).")
    parser.add_argument("--concurrency", type=int, default=6,
                        help="Parallel uploads (batch mode); default 6.")
    parser.add_argument("--timeout", type=float, default=300.0,
                        help="Per-request timeout in seconds (default 300).")
    parser.add_argument("--base-url", help="Override server URL.")
    parser.add_argument("--api-key", help="Bearer token (optional).")
    parser.add_argument("--insecure", action="store_true",
                        help="Disable TLS verification (also auto-disabled for hostnames containing '_').")
    parser.add_argument("--list-models", action="store_true",
                        help="List models on the server and exit.")
    args = parser.parse_args()

    cfg = load_config()
    base_url = args.base_url or cfg["base_url"]
    api_key = args.api_key if args.api_key is not None else cfg["api_key"]

    if not base_url:
        parser.error(
            "Speaches base URL not set. Configure via --base-url, "
            "the SPEACHES_BASE_URL env var, or config/settings.yaml."
        )
    verify = resolve_verify(base_url, args.insecure)

    if args.list_models:
        return list_models(base_url, api_key, verify)

    prompt = args.prompt
    if args.bilingual_prompt:
        if prompt:
            print("[err] --prompt and --bilingual-prompt are mutually exclusive", file=sys.stderr)
            return 2
        prompt = BILINGUAL_PROMPT

    files = gather_audio(args.files, args.dir)
    if not files:
        parser.error("Pass audio files or --dir")

    # Validate convert dependency upfront so we don't fail mid-batch.
    if args.convert and not shutil.which("opencc"):
        print("[err] opencc not found. brew install opencc", file=sys.stderr)
        return 2

    print(f"[speaches] {base_url} model={args.model} files={len(files)}", file=sys.stderr)

    if len(files) == 1 and not args.output_dir:
        # Single-file mode
        src = files[0]
        result = transcribe_file(
            src,
            base_url=base_url, api_key=api_key,
            model=args.model, language=args.language,
            prompt=prompt, response_format=args.response_format,
            convert=args.convert, timeout=args.timeout,
            verify=verify,
        )
        if args.output:
            out = Path(args.output)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
            print(f"[ok] {src.name} → {out}", file=sys.stderr)
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    # Batch mode
    if not args.output_dir:
        parser.error("--output-dir is required in batch mode (multiple files or --dir)")
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    failures: list[tuple[Path, str]] = []
    successes = 0
    t0 = time.time()

    def _job(src: Path) -> tuple[Path, dict | str]:
        try:
            result = transcribe_file(
                src,
                base_url=base_url, api_key=api_key,
                model=args.model, language=args.language,
                prompt=prompt, response_format=args.response_format,
                convert=args.convert, timeout=args.timeout,
                verify=verify,
            )
            return src, result
        except Exception as e:
            return src, str(e)

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        for src, result in ex.map(_job, files):
            if isinstance(result, str):
                failures.append((src, result))
                print(f"[err] {src.name}: {result}", file=sys.stderr)
                continue
            out = output_path_for(src, out_dir)
            out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
            successes += 1
            print(f"[ok] {src.name} → {out.name}", file=sys.stderr)

    elapsed = time.time() - t0
    print(f"[done] {successes}/{len(files)} in {elapsed:.1f}s", file=sys.stderr)
    if failures:
        print(f"[fail] {len(failures)} file(s) failed:", file=sys.stderr)
        for src, err in failures:
            print(f"   {src.name}: {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

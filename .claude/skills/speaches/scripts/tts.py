#!/usr/bin/env python3
"""Synthesize speech via a speaches server (OpenAI-compatible /v1/audio/speech).

Examples:
  tts.py --text "Hello world" --voice af_bella -o hello.mp3
  tts.py --list-voices
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

import requests
import urllib3
import yaml


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
DEFAULT_MODEL = "speaches-ai/Kokoro-82M-v1.0-ONNX-int8"
DEFAULT_VOICE = "af_heart"
FORMAT_TO_EXT = {"mp3": "mp3", "wav": "wav", "flac": "flac", "pcm": "pcm", "opus": "opus", "aac": "aac"}


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
    """Auto-disable TLS verification for hostnames containing '_' (RFC 1123 invalid)."""
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


def fetch_voices(base_url: str, api_key: str, model: str, verify: bool) -> list[dict]:
    resp = requests.get(
        f"{base_url.rstrip('/')}/v1/models",
        headers=auth_headers(api_key),
        timeout=20,
        verify=verify,
    )
    resp.raise_for_status()
    for m in resp.json().get("data", []):
        if m.get("id") == model:
            return m.get("voices", [])
    return []


def list_voices(base_url: str, api_key: str, model: str, verify: bool) -> int:
    voices = fetch_voices(base_url, api_key, model, verify)
    if not voices:
        print(f"[err] no voices found for model {model}", file=sys.stderr)
        return 1
    print(f"{len(voices)} voice(s) on {model}\n")
    for v in voices:
        name = v.get("name", "")
        lang = v.get("language", "")
        gender = v.get("gender", "")
        print(f"  {name:20s} {lang:10s} {gender}")
    return 0


def synthesize(
    text: str,
    *,
    base_url: str,
    api_key: str,
    model: str,
    voice: str,
    fmt: str,
    speed: float,
    timeout: float,
    verify: bool,
) -> bytes:
    url = f"{base_url.rstrip('/')}/v1/audio/speech"
    headers = {
        "Content-Type": "application/json",
        **auth_headers(api_key),
    }
    payload = {
        "model": model,
        "input": text,
        "voice": voice,
        "response_format": fmt,
        "speed": speed,
    }
    resp = requests.post(url, headers=headers, data=json.dumps(payload),
                         timeout=timeout, verify=verify)
    if resp.status_code >= 300:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:400]}")
    return resp.content


def main() -> int:
    parser = argparse.ArgumentParser(description="Synthesize speech via a speaches server.")
    parser.add_argument("--text", help="Text to synthesize")
    parser.add_argument("--file", help="Read text from a file")
    parser.add_argument("--voice", default=DEFAULT_VOICE, help=f"Voice name (default: {DEFAULT_VOICE})")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Model id (default: {DEFAULT_MODEL})")
    parser.add_argument("--format", dest="fmt", default="mp3",
                        choices=list(FORMAT_TO_EXT.keys()))
    parser.add_argument("--speed", type=float, default=1.0, help="0.25 to 4.0 (default 1.0)")
    parser.add_argument("--output", "-o", help="Output file (default tts.<format>)")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--base-url", help="Override server URL.")
    parser.add_argument("--api-key", help="Bearer token (optional).")
    parser.add_argument("--insecure", action="store_true",
                        help="Disable TLS verification (also auto-disabled for hostnames containing '_').")
    parser.add_argument("--list-voices", action="store_true", help="List voices and exit.")
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

    if args.list_voices:
        return list_voices(base_url, api_key, args.model, verify)

    if args.text and args.file:
        parser.error("Pass --text or --file, not both.")
    if args.file:
        text = Path(args.file).read_text()
    else:
        text = args.text
    if not text:
        parser.error("--text or --file required.")

    audio = synthesize(
        text,
        base_url=base_url, api_key=api_key,
        model=args.model, voice=args.voice,
        fmt=args.fmt, speed=args.speed, timeout=args.timeout,
        verify=verify,
    )
    out = Path(args.output or f"tts.{FORMAT_TO_EXT[args.fmt]}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(audio)
    print(json.dumps({"success": True, "voice": args.voice, "format": args.fmt,
                      "bytes": len(audio), "path": str(out)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())

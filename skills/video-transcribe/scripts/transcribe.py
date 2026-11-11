#!/usr/bin/env python3
"""Transcribe a video URL (anything yt-dlp supports) or a local audio/video file.

Strategy: use the platform's own subtitles when they exist (fast, free),
otherwise download the audio only and run Whisper locally.
Nothing is uploaded anywhere; only yt-dlp and Whisper model downloads touch the network.

Standard library only (Python 3.9+). External commands: yt-dlp, ffmpeg, and one of
mlx_whisper / whisper-ctranslate2 / whisper.
"""
from __future__ import annotations

import argparse
import datetime
import glob
import html
import json
import os
import re
import shutil
import subprocess
import sys

DEFAULT_OUT = os.path.join(
    os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache")), "video-transcribe"
)
LOOP_RUN = 8  # this many identical captions in a row means Whisper is looping

# (command, default model, argument builder). First one found on PATH wins.
BACKENDS = [
    (
        "mlx_whisper",  # Apple Silicon
        "mlx-community/whisper-large-v3-turbo",
        lambda audio, model, outdir, lang: [
            "mlx_whisper", audio, "--model", model, "--output-dir", outdir,
            "--output-name", "whisper", "--output-format", "srt",
            "--condition-on-previous-text", "False",
        ] + (["--language", lang] if lang else []),
    ),
    (
        "whisper-ctranslate2",  # faster-whisper, any platform
        "large-v3-turbo",
        lambda audio, model, outdir, lang: [
            "whisper-ctranslate2", audio, "--model", model, "--output_dir", outdir,
            "--output_format", "srt", "--condition_on_previous_text", "False",
            "--vad_filter", "True",
        ] + (["--language", lang] if lang else []),
    ),
    (
        "whisper",  # openai-whisper
        "turbo",
        lambda audio, model, outdir, lang: [
            "whisper", audio, "--model", model, "--output_dir", outdir,
            "--output_format", "srt", "--condition_on_previous_text", "False",
        ] + (["--language", lang] if lang else []),
    ),
]


def log(msg: str) -> None:
    print(f"[video-transcribe] {msg}", file=sys.stderr, flush=True)


def fail(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def run(cmd: list[str], quiet: bool = True) -> str:
    log("$ " + " ".join(cmd))
    proc = subprocess.run(
        cmd, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE if quiet else None,
    )
    if proc.returncode != 0:
        tail = (proc.stderr or "").strip().splitlines()[-5:] if quiet else []
        fail(f"{cmd[0]} exited with {proc.returncode}\n" + "\n".join(tail))
    return proc.stdout


def need(cmd: str, hint: str) -> None:
    if not shutil.which(cmd):
        fail(f"'{cmd}' not found. Install it: {hint}")


def slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", text).strip("-")[:80] or "video"


def secs(stamp: str) -> float:
    parts = stamp.strip().replace(",", ".").split(":")
    return sum(float(p) * m for p, m in zip(reversed(parts), (1, 60, 3600)))


def hms(x: float) -> str:
    x = int(x)
    return f"{x // 3600:02}:{x % 3600 // 60:02}:{x % 60:02}"


def parse_cues(path: str) -> list[tuple[float, str]]:
    """Parse VTT or SRT into (start_seconds, text), dropping rolling-caption repeats."""
    with open(path, encoding="utf-8") as f:
        raw = f.read().replace("\r\n", "\n")
    out: list[tuple[float, str]] = []
    recent: list[str] = []
    for block in re.split(r"\n{2,}", raw):
        lines = block.strip().splitlines()
        cue = next((i for i, l in enumerate(lines) if "-->" in l), None)
        if cue is None:
            continue
        start = secs(lines[cue].split("-->")[0])
        fresh = []
        for line in lines[cue + 1:]:
            text = html.unescape(re.sub(r"<[^>]+>", "", line)).strip()
            # YouTube auto-captions repeat the previous line in each new cue.
            if not text or text in recent:
                continue
            fresh.append(text)
            recent = (recent + [text])[-2:]
        if fresh:
            out.append((start, join(fresh)))
    return out


def join(parts: list[str]) -> str:
    """Join caption lines; no space between two non-ASCII (e.g. Japanese) ends."""
    text = parts[0]
    for part in parts[1:]:
        sep = "" if not text[-1].isascii() and not part[0].isascii() else " "
        text += sep + part
    return text


def find_loops(cues: list[tuple[float, str]]) -> list[str]:
    warnings, i = [], 0
    while i < len(cues):
        j = i
        while j + 1 < len(cues) and cues[j + 1][1] == cues[i][1]:
            j += 1
        if j - i + 1 >= LOOP_RUN:
            warnings.append(
                f"possible Whisper loop {hms(cues[i][0])}-{hms(cues[j][0])}: "
                f"{cues[i][1][:40]!r} x{j - i + 1}"
            )
        i = j + 1
    return warnings


def pick_subtitle(meta: dict, langs: list[str]) -> tuple[str, str] | None:
    """Return (kind, track) for the best subtitle, or None.

    Order: human subtitles in a preferred language, human subtitles in the spoken
    language, then auto-captions in the spoken language. Auto-translated captions
    are never used: they are a machine translation, not a transcript.
    """
    manual = {k: v for k, v in (meta.get("subtitles") or {}).items() if k != "live_chat"}
    auto = meta.get("automatic_captions") or {}
    spoken = (meta.get("language") or "").split("-")[0]

    def match(tracks: dict, lang: str) -> str | None:
        for key in tracks:
            if key == lang or key.startswith(lang + "-"):
                return key
        return None

    for lang in langs:
        key = match(manual, lang)
        if key:
            return "subtitles", key
    if spoken and match(manual, spoken):
        return "subtitles", match(manual, spoken)
    # Auto-dubbed videos have one "-orig" track per audio track (e.g. ja-orig and
    # en-US-orig); only the one in the spoken language is what was actually said.
    orig = [k for k in auto if k.endswith("-orig")]
    if not spoken:
        return ("auto-captions", orig[0]) if orig else None
    for key in orig:
        if key.split("-")[0] == spoken:
            return "auto-captions", key
    if spoken in auto:
        return "auto-captions", spoken
    return None


def whisper(audio: str, workdir: str, model: str | None, lang: str | None) -> tuple[str, str, str]:
    need("ffmpeg", "brew install ffmpeg (macOS) / apt install ffmpeg")
    for cmd, default_model, build in BACKENDS:
        if shutil.which(cmd):
            model = model or default_model
            for old in glob.glob(os.path.join(workdir, "*.srt")):
                os.remove(old)
            run(build(audio, model, workdir, lang), quiet=False)
            srts = glob.glob(os.path.join(workdir, "*.srt"))
            if not srts:
                fail(f"{cmd} finished but wrote no .srt file")
            return srts[0], cmd, model
    fail(
        "no Whisper found. Install one: `uv tool install mlx-whisper` (Apple Silicon) "
        "or `uv tool install whisper-ctranslate2` (other platforms)"
    )
    raise AssertionError  # unreachable


def build_markdown(info: dict, lines: list[str]) -> str:
    """Render the transcript as Markdown with OKF (Open Knowledge Format) frontmatter."""
    title = info.get("title") or "Untitled video"
    by = f" by {info['uploader']}" if info.get("uploader") else ""
    date = info.get("upload_date") or ""
    if re.fullmatch(r"\d{8}", date):
        date = f"{date[:4]}-{date[4:6]}-{date[6:]}"
    fields = {
        "type": "reference",
        "title": title,
        "description": f"Transcript of the video \"{title}\"{by}.",
        "tags": ["transcript"],
        "timestamp": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "source": info.get("source"),
        "uploader": info.get("uploader"),
        "duration": info.get("duration"),
        "upload_date": date or None,
        "method": info.get("method"),
        "language": info.get("language"),
    }
    # JSON strings and arrays are valid YAML, so json.dumps quotes values safely.
    out = ["---"] + [f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in fields.items() if v]
    out += ["---", "", f"# {title}", ""]
    chapters = list(info.get("chapters") or [])
    for line in lines:
        # Lines start with "[hh:mm:ss]", so zero-padded times compare as strings.
        while chapters and line[1:9] >= chapters[0]["start"]:
            out += ["", f"## {chapters.pop(0)['title']}", ""]
        out.append(f"- {line}")
    return "\n".join(out).replace("\n\n\n", "\n\n") + "\n"


def save_markdown(info: dict, txt_path: str, save_dir: str, key: str, force: bool) -> str:
    path = os.path.join(save_dir, key + ".md")
    if os.path.exists(path) and not force:
        log(f"{path} already exists; pass --force to overwrite it")
        return path
    with open(txt_path, encoding="utf-8") as f:
        lines = [l.rstrip("\n") for l in f if l.strip()]
    os.makedirs(save_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(build_markdown(info, lines))
    return path


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("source", help="video URL or local audio/video file")
    ap.add_argument("--lang", default="en",
                    help="preferred subtitle languages, comma-separated, in priority order (default: en)")
    ap.add_argument("--whisper", action="store_true",
                    help="skip platform subtitles and always transcribe the audio")
    ap.add_argument("--model", help="Whisper model (default depends on backend)")
    ap.add_argument("--spoken-lang", help="spoken language hint for Whisper, e.g. ja")
    ap.add_argument("--out", default=DEFAULT_OUT, help=f"output root (default: {DEFAULT_OUT})")
    ap.add_argument("--keep-audio", action="store_true", help="keep the downloaded audio")
    ap.add_argument("--save", metavar="DIR",
                    help="also save the transcript as Markdown with OKF frontmatter in DIR")
    ap.add_argument("--force", action="store_true",
                    help="ignore a cached transcript and overwrite a saved Markdown file")
    args = ap.parse_args()
    langs = [l.strip() for l in args.lang.split(",") if l.strip()]
    # `uv tool install` / `pipx install` put commands here, which is often not on PATH.
    os.environ["PATH"] += os.pathsep + os.path.expanduser("~/.local/bin")

    is_file = os.path.isfile(args.source)
    meta: dict = {}
    if is_file:
        source = os.path.abspath(args.source)
        key = "file-" + slug(os.path.splitext(os.path.basename(source))[0]).lower()
        meta = {"title": os.path.basename(source)}
    else:
        need("yt-dlp", "brew install yt-dlp / pipx install yt-dlp")
        source = args.source
        meta = json.loads(run(["yt-dlp", "--dump-single-json", "--skip-download",
                               "--no-playlist", source]))
        key = slug(f"{meta.get('extractor_key', 'web')}-{meta.get('id', 'video')}").lower()

    workdir = os.path.join(args.out, key)
    os.makedirs(workdir, exist_ok=True)
    txt_path = os.path.join(workdir, "transcript.txt")
    info_path = os.path.join(workdir, "info.json")

    if os.path.exists(txt_path) and os.path.exists(info_path) and not args.force:
        log("using cached transcript (pass --force to redo)")
        with open(info_path, encoding="utf-8") as f:
            info = json.load(f)
    else:
        info = transcribe(args, source, meta, is_file, langs, workdir, txt_path)
        with open(info_path, "w", encoding="utf-8") as f:
            json.dump(info, f, ensure_ascii=False, indent=2)
    if args.save:
        info["saved"] = save_markdown(info, txt_path, args.save, key, args.force)
    print(json.dumps(info, ensure_ascii=False, indent=2))


def transcribe(args, source: str, meta: dict, is_file: bool, langs: list[str],
               workdir: str, txt_path: str) -> dict:
    info = {
        "source": source,
        "title": meta.get("title"),
        "uploader": meta.get("uploader") or meta.get("channel"),
        "duration": hms(meta["duration"]) if meta.get("duration") else None,
        "upload_date": meta.get("upload_date"),
        "chapters": [
            {"start": hms(c["start_time"]), "title": c.get("title")}
            for c in meta.get("chapters") or []
        ] or None,
    }

    track = None if (is_file or args.whisper) else pick_subtitle(meta, langs)
    if track:
        kind, lang = track
        flag = "--write-subs" if kind == "subtitles" else "--write-auto-subs"
        for old in glob.glob(os.path.join(workdir, "subs.*")):
            os.remove(old)
        run(["yt-dlp", "--skip-download", "--no-playlist", flag, "--sub-langs", lang,
             "--sub-format", "vtt/srt/best", "-o", os.path.join(workdir, "subs.%(ext)s"), source])
        files = glob.glob(os.path.join(workdir, "subs.*"))
        if not files:
            fail(f"yt-dlp did not write the {lang} {kind}")
        cues = parse_cues(files[0])
        info.update(method=kind, language=lang)
    else:
        audio = source
        if not is_file:
            for old in glob.glob(os.path.join(workdir, "audio.*")):
                os.remove(old)
            # Prefer the original audio over auto-dubbed tracks.
            run(["yt-dlp", "-f", "bestaudio[format_note*=original]/bestaudio/best", "--no-playlist",
                 "-o", os.path.join(workdir, "audio.%(ext)s"), source])
            audio = glob.glob(os.path.join(workdir, "audio.*"))[0]
        spoken = args.spoken_lang or (meta.get("language") or "").split("-")[0] or None
        srt, backend, model = whisper(audio, workdir, args.model, spoken)
        cues = parse_cues(srt)
        info.update(method="whisper", language=spoken or "auto-detected",
                    backend=backend, model=model)
        if not is_file and not args.keep_audio:
            os.remove(audio)

    with open(txt_path, "w", encoding="utf-8") as f:
        f.writelines(f"[{hms(start)}] {text}\n" for start, text in cues)
    info.update(
        transcript=txt_path,
        lines=len(cues),
        characters=sum(len(t) for _, t in cues),
        warnings=find_loops(cues) if info["method"] == "whisper" else [],
    )
    return info


if __name__ == "__main__":
    main()

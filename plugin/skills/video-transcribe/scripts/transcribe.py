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
import bisect
import datetime
import decimal
import glob
import html
import json
import math
import os
import pathlib
import re
import shutil
import subprocess
import sys
import unicodedata

VERSION = "0.2.0"  # bump on each release; a test checks it against CHANGELOG.md
DEFAULT_OUT = os.path.join(
    os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache")), "video-transcribe"
)
LOOP_RUN = 8  # this many identical captions in a row means Whisper is looping
# Two Whisper models place the same words up to several seconds apart, so a line of the
# first transcript is compared with the second transcript from BEFORE to AFTER seconds around it.
BEFORE, AFTER = 8, 12
CUE_MAX = 30  # Whisper works in 30-second windows, so no cue lasts longer
# Where the second model has nothing, this much before and after is cut out and transcribed again.
CLIP_BEFORE, CLIP_AFTER = 5, 15

# (command, default model, second model for --recheck, argument builder).
# First one found on PATH wins.
# "--" ends option parsing, so a file name starting with "-" is never read as an option.
BACKENDS = [
    (
        "mlx_whisper",  # Apple Silicon
        "mlx-community/whisper-large-v3-turbo",
        "mlx-community/whisper-large-v3-mlx",
        lambda audio, model, outdir, lang: [
            "mlx_whisper", "--model", model, "--output-dir", outdir,
            "--output-name", "whisper", "--output-format", "srt",
            "--condition-on-previous-text", "False",
        ] + (["--language", lang] if lang else []) + ["--", audio],
    ),
    (
        "whisper-ctranslate2",  # faster-whisper, any platform
        "large-v3-turbo",
        "large-v3",
        lambda audio, model, outdir, lang: [
            "whisper-ctranslate2", "--model", model, "--output_dir", outdir,
            "--output_format", "srt", "--condition_on_previous_text", "False",
            "--vad_filter", "True",
        ] + (["--language", lang] if lang else []) + ["--", audio],
    ),
    (
        "whisper",  # openai-whisper
        "turbo",
        "large-v3",
        lambda audio, model, outdir, lang: [
            "whisper", "--model", model, "--output_dir", outdir,
            "--output_format", "srt", "--condition_on_previous_text", "False",
        ] + (["--language", lang] if lang else []) + ["--", audio],
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


def parse_cues(path: str, rolling: bool = False) -> list[tuple[float, str]]:
    """Parse VTT or SRT into (start_seconds, text); see parse_timed for rolling."""
    return [(start, text) for start, _, text in parse_timed(path, rolling)]


def parse_timed(path: str, rolling: bool = False) -> list[tuple[float, float, str]]:
    """Parse VTT or SRT into (start, end, text) in seconds.

    With rolling, a line that repeats one of the two lines before it is dropped: YouTube
    auto-captions repeat the previous line in each new cue. Whisper output is read without
    it, so a line Whisper repeats (a loop, or a real "yes, yes") stays and can be counted.
    """
    with open(path, encoding="utf-8") as f:
        raw = f.read().replace("\r\n", "\n")
    out: list[tuple[float, float, str]] = []
    recent: list[str] = []
    for block in re.split(r"\n{2,}", raw):
        lines = block.strip().splitlines()
        cue = next((i for i, l in enumerate(lines) if "-->" in l), None)
        if cue is None:
            continue
        # VTT may put cue settings after the end time: "00:01.000 --> 00:03.000 align:start"
        start, end = (secs(x.split()[0]) for x in lines[cue].split("-->"))
        fresh = []
        for line in lines[cue + 1:]:
            text = html.unescape(re.sub(r"<[^>]+>", "", line)).strip()
            if not text or (rolling and text in recent):
                continue
            fresh.append(text)
            recent = (recent + [text])[-2:]
        if fresh:
            out.append((start, end, join(fresh)))
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


def backend() -> tuple:
    need("ffmpeg", "brew install ffmpeg (macOS) / apt install ffmpeg")
    for entry in BACKENDS:
        if shutil.which(entry[0]):
            return entry
    fail(
        "no Whisper found. Install one: `uv tool install mlx-whisper` (Apple Silicon) "
        "or `uv tool install whisper-ctranslate2` (other platforms)"
    )
    raise AssertionError  # unreachable


def whisper(audio: str, workdir: str, model: str | None, lang: str | None) -> tuple[str, str, str]:
    cmd, default_model, _, build = backend()
    model = model or default_model
    for old in glob.glob(os.path.join(workdir, "*.srt")):
        os.remove(old)
    run(build(audio, model, workdir, lang), quiet=False)
    srts = glob.glob(os.path.join(workdir, "*.srt"))
    if not srts:
        fail(f"{cmd} finished but wrote no .srt file")
    return srts[0], cmd, model


def fetch_audio(source: str, is_file: bool, workdir: str) -> str:
    if is_file:
        return source
    for old in glob.glob(os.path.join(workdir, "audio.*")):
        os.remove(old)
    # Prefer the original audio over auto-dubbed tracks.
    run(["yt-dlp", "-f", "bestaudio[format_note*=original]/bestaudio/best", "--no-playlist",
         "-o", os.path.join(workdir, "audio.%(ext)s"), "--", source])
    return glob.glob(os.path.join(workdir, "audio.*"))[0]


LINE = re.compile(r"\[(\d+):(\d\d):(\d\d)(?:-(\d+):(\d\d):(\d\d))?\] ?(.*)")


def read_lines(path: str) -> list[tuple[float, float | None, str]]:
    """Read "[hh:mm:ss] text" or "[hh:mm:ss-hh:mm:ss] text" lines into (start, end, text)."""
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            m = LINE.match(line.strip())
            if m:
                g = m.groups()
                start = int(g[0]) * 3600 + int(g[1]) * 60 + int(g[2])
                end = int(g[3]) * 3600 + int(g[4]) * 60 + int(g[5]) if g[3] else None
                out.append((start, end, g[6]))
    return out


def write_lines(path: str, cues: list[tuple]) -> None:
    """Write (start, text) as "[hh:mm:ss] text", or (start, end, text) with the end too."""
    with open(path, "w", encoding="utf-8") as f:
        for cue in cues:
            stamp = hms(cue[0]) + (f"-{hms(math.ceil(cue[1]))}" if len(cue) == 3 else "")
            f.write(f"[{stamp}] {cue[-1]}\n")


# --- --recheck: compare with a second Whisper model -------------------------------------

def spans(cues: list[tuple[float, float | None, str]]) -> list[tuple[float, float, str]]:
    """Fill in missing ends: the next cue's start, but at most CUE_MAX seconds later."""
    out = []
    for i, (start, end, text) in enumerate(cues):
        if end is None:
            nxt = cues[i + 1][0] if i + 1 < len(cues) else start + CUE_MAX
            end = min(nxt, start + CUE_MAX)
        out.append((start, end, text))
    return out


def overlapping(timed: list[tuple[float, float, str]], a: float, b: float) -> list[tuple[float, float, str]]:
    """The spans (sorted by start) that overlap the time range [a, b]."""
    lo = bisect.bisect_left(timed, (a - CUE_MAX,))
    hi = bisect.bisect_right(timed, (b, float("inf")))
    return [x for x in timed[lo:hi] if x[1] >= a]


KANJI_DIGITS = {c: i for i, c in enumerate("〇一二三四五六七八九")} | {"零": 0}
KANJI_SMALL = {"十": 10, "百": 100, "千": 1000}
KANJI_BIG = {"万": 10 ** 4, "億": 10 ** 8, "兆": 10 ** 12}
KANJI_NUMERALS = "".join(KANJI_DIGITS) + "".join(KANJI_SMALL) + "".join(KANJI_BIG)
NUMBER = re.compile(f"[0-9{KANJI_NUMERALS}][0-9,.{KANJI_NUMERALS}]*")


def parse_number(token: str) -> decimal.Decimal | None:
    """Read one number written in digits, kanji, or both: 9万7千, 9万7000, 二十三, 1.5."""
    total = section = decimal.Decimal(0)
    current = None
    for part in re.findall(r"[0-9.]+|.", token):
        if part[0] in "0123456789.":
            try:
                current = decimal.Decimal(part)
            except decimal.InvalidOperation:
                return None
        elif part in KANJI_DIGITS:
            current = (current or 0) * 10 + KANJI_DIGITS[part]  # positional, e.g. 二〇二三
        elif part in KANJI_SMALL:
            section += (1 if current is None else current) * KANJI_SMALL[part]
            current = None
        else:
            total += ((section + (current or 0)) or 1) * KANJI_BIG[part]
            section, current = decimal.Decimal(0), None
    return total + section + (current or 0)


def numbers(text: str, digits_only: bool = False) -> set[decimal.Decimal]:
    """The values of the numbers in text, so that 9万7千 and 9万7000 count as the same.

    With digits_only, numbers written only in kanji are skipped: kanji digits also appear
    in ordinary words (一緒, 千葉), so they are used only to match, never reported.
    """
    found = set()
    for token in NUMBER.findall(unicodedata.normalize("NFKC", text)):
        token = token.rstrip(",.")
        if digits_only and not re.search(r"[0-9]", token):
            continue
        # A comma before exactly three digits groups thousands; any other comma lists
        # numbers, as in "4,5本" (four or five).
        token = re.sub(r"(?<=[0-9]),(?=[0-9]{3}(?![0-9]))", "", token)
        for part in token.split(","):
            value = parse_number(part) if part else None
            if value is not None:
                found.add(value)
    return found


def show_number(value: decimal.Decimal) -> str:
    return format(value.normalize(), "f")


def nearest(starts: list[float], t: float) -> int:
    """Index of the start time closest to t (starts sorted, not empty)."""
    i = bisect.bisect_left(starts, t)
    if i == len(starts) or (i > 0 and t - starts[i - 1] <= starts[i] - t):
        i -= 1
    return max(i, 0)


def uncovered(first: list[tuple], second: list[tuple[float, float, str]]) -> list[float]:
    """Times of first-transcript lines with nothing in the second transcript around them."""
    return [c[0] for c in first if not overlapping(second, c[0] - BEFORE, c[0] + AFTER)]


def time_ranges(times: list[float], gap: float) -> list[tuple[float, float]]:
    """Merge sorted times that are at most gap seconds apart into (first, last) ranges."""
    out: list[tuple[float, float]] = []
    for t in times:
        if out and t - out[-1][1] <= gap:
            out[-1] = (out[-1][0], t)
        else:
            out.append((t, t))
    return out


def build_recheck(info: dict, first: list[tuple], second: list[tuple]) -> tuple[str, dict]:
    """Render recheck.md, which lays the second transcript beside the first.

    Both transcripts are lists of (start, end or None, text) sorted by start.
    """
    timed1, timed2 = spans(first), spans(second)
    starts = [c[0] for c in first]

    def around(i: int) -> list:  # the second transcript around line i of the first
        return overlapping(timed2, starts[i] - BEFORE, starts[i] + AFTER)

    def unmatched(text: str, near: list) -> set:
        return numbers(text, digits_only=True) - numbers(" ".join(x[2] for x in near))

    # Numbers in one transcript that the other does not have around the same time,
    # looked for in both directions. Where the other has nothing at all, nothing is compared.
    only1: dict[int, set] = {}
    only2: dict[int, set] = {}
    shown2: dict[int, set] = {}  # second-transcript lines to show with line i of the first
    for i, (_, _, text) in enumerate(timed1):
        near = around(i)
        missing = unmatched(text, near)
        if near and missing:
            only1[i] = missing
            shown2.setdefault(i, set()).update(near)
    for cue in timed2:
        s, e, text = cue
        near = overlapping(timed1, s - AFTER, e + BEFORE)
        missing = unmatched(text, near)
        if near and missing:
            i = nearest(starts, s)
            only2.setdefault(i, set()).update(missing)
            shown2.setdefault(i, set()).update(around(i) + [cue])
    flagged = sorted(only1.keys() | only2.keys())

    gaps = time_ranges(uncovered(first, timed2), BEFORE + AFTER)
    first_label = info.get("method") or "unknown"
    if info.get("model"):
        first_label += f", {info['model']}"
    out = [
        f"# Recheck: {info.get('title') or 'Untitled video'}",
        "",
        f"- First transcript: `transcript.txt` ({first_label})",
        f"- Second transcript: `recheck.txt` ({info['recheck']['model']})",
        f"- Around each line of the first transcript, the second is read from {BEFORE} seconds "
        f"before to {AFTER} seconds after it, because the two place the same words a few seconds apart.",
        "",
        f"## Numbers that differ ({len(flagged)})",
        "",
    ]
    if not flagged:
        out += ["None.", ""]
    for i in flagged:
        out += [f"### [{hms(starts[i])}]", "", f"- First: {first[i][2]}", "- Second:"]
        out += [f"  - [{hms(s)}] {x}" for s, _, x in sorted(shown2[i])]
        if i in only1:
            out.append("- Only in the first: " + ", ".join(sorted(map(show_number, only1[i]))))
        if i in only2:
            out.append("- Only in the second: " + ", ".join(sorted(map(show_number, only2[i]))))
        out.append("")
    out += [f"## Not covered by the second transcript ({len(gaps)})", ""]
    if gaps:
        out += ["The second transcript has nothing around these lines of the first, "
                "so it cannot confirm or question them.", ""]
        out += [f"- {hms(a)}-{hms(b)}" for a, b in gaps]
    else:
        out.append("None.")
    out += [
        "",
        "## Side by side",
        "",
        "Each line of the first transcript, with the lines of the second transcript that start "
        "closest to it indented under it.",
        "",
    ]
    nested: dict[int, list] = {}
    for s, _, x in second:
        nested.setdefault(nearest(starts, s), []).append((s, x))
    for i, (t, _, text) in enumerate(first):
        out.append(f"- [{hms(t)}] {text}")
        out += [f"  - [{hms(s)}] {x}" for s, x in nested.get(i, [])]
    stats = {
        "numbers_differ": len(flagged),
        "not_covered": [f"{hms(a)}-{hms(b)}" for a, b in gaps],
        "warnings": find_loops([(s, x) for s, _, x in second]),
    }
    return "\n".join(out) + "\n", stats


def recheck(args, info: dict, get_audio, workdir: str, txt_path: str) -> dict:
    """Transcribe again with a second Whisper model and write recheck.md."""
    if info.get("method") == "subtitles":
        fail("--recheck compares two machine transcripts; this one comes from human-made subtitles")
    second_path = os.path.join(workdir, "recheck.txt")
    first = read_lines(txt_path)
    done = info.get("recheck") or {}
    if args.force or not done.get("model") or not os.path.exists(second_path):
        cmd, _, model, _ = backend()
        if info.get("model") == model:
            # The same model would agree with itself everywhere and confirm nothing.
            fail(f"the transcript was already made with {model}; transcribe it again with "
                 "--force and the default model, then pass --recheck")
        lang = args.spoken_lang or (info.get("language") or "").split("-")[0]
        lang = None if lang in ("", "auto") else lang  # "auto-detected"
        outdir = os.path.join(workdir, "recheck")
        os.makedirs(outdir, exist_ok=True)
        audio = get_audio()
        second = parse_timed(whisper(audio, outdir, model, lang)[0])
        # The second model can drop stretches, often the first and last minutes. Cut those
        # out and transcribe them one by one (mlx_whisper ignores --clip-timestamps and
        # writes only the first result when given several files).
        for a, b in time_ranges(uncovered(first, second), CLIP_BEFORE + CLIP_AFTER):
            a, b = max(a - CLIP_BEFORE, 0), b + CLIP_AFTER
            clip = os.path.join(outdir, "clip.wav")
            run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-ss", str(a), "-to", str(b),
                 "-i", audio, "-ac", "1", "-ar", "16000", clip])
            second += [(a + s, a + e, x) for s, e, x in parse_timed(whisper(clip, outdir, model, lang)[0])]
            os.remove(clip)
        second.sort()
        write_lines(second_path, second)
        done = {"backend": cmd, "model": model, "transcript": second_path}
    info["recheck"] = done
    md, stats = build_recheck(info, first, read_lines(second_path))
    report = os.path.join(workdir, "recheck.md")
    with open(report, "w", encoding="utf-8") as f:
        f.write(md)
    return dict(done, report=report, **stats)


def resource_uri(info: dict) -> str | None:
    """The video as a URI: its page URL, or a file: URI for a local file."""
    target = info.get("url") or info.get("source")
    # OKF reads a bare "/path" as a path inside the bundle, so local files need a file: URI.
    if target and os.path.isabs(target):
        return pathlib.Path(target).as_uri()
    return target


def build_markdown(info: dict, lines: list[str]) -> str:
    """Render the transcript as Markdown with OKF (Open Knowledge Format) v0.3 frontmatter."""
    title = info.get("title") or "Untitled video"
    by = f" by {info['uploader']}" if info.get("uploader") else ""
    date = info.get("upload_date") or ""
    if re.fullmatch(r"\d{8}", date):
        date = f"{date[:4]}-{date[4:6]}-{date[6:]}"
    now = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    # OKF keys that apply to any type are always written, null where there is no value,
    # so a reader that expects every key finds them. "stable" is OKF's default status.
    okf = {
        "type": "Reference",
        "title": title,
        "description": f"Transcript of the video \"{title}\"{by}.",
        "resource": resource_uri(info),
        "tags": ["transcript"],
        "generated": {"by": f"video-transcribe/{VERSION}", "at": now},
        "verified": None,
        "sources": None,
        "status": "stable",
        "stale_after": None,
        "superseded_by": None,
    }
    # Keys outside OKF get the x-<producer>- prefix, which OKF never uses for its own keys,
    # and are written only when there is a value.
    extra = {
        "x-video-transcribe-uploader": info.get("uploader"),
        "x-video-transcribe-duration": info.get("duration"),
        "x-video-transcribe-upload-date": date or None,
        "x-video-transcribe-method": info.get("method"),
        "x-video-transcribe-language": info.get("language"),
    }
    fields = {**okf, **{k: v for k, v in extra.items() if v}}
    # JSON strings, arrays, and null are valid YAML, so json.dumps quotes values safely.
    out = ["---"] + [f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in fields.items()]
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
    ap.add_argument("--recheck", action="store_true",
                    help="also transcribe with a second, larger Whisper model and write recheck.md, "
                         "which lays the two side by side to find misheard words")
    ap.add_argument("--version", action="version", version=f"video-transcribe {VERSION}")
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
                               "--no-playlist", "--", source]))
        key = slug(f"{meta.get('extractor_key', 'web')}-{meta.get('id', 'video')}").lower()

    workdir = os.path.join(args.out, key)
    os.makedirs(workdir, exist_ok=True)
    txt_path = os.path.join(workdir, "transcript.txt")
    info_path = os.path.join(workdir, "info.json")

    audio: list[str] = []  # downloaded at most once, then shared by both Whisper runs

    def get_audio() -> str:
        if not audio:
            audio.append(fetch_audio(source, is_file, workdir))
        return audio[0]

    if os.path.exists(txt_path) and os.path.exists(info_path) and not args.force:
        log("using cached transcript (pass --force to redo)")
        with open(info_path, encoding="utf-8") as f:
            info = json.load(f)
    else:
        info = transcribe(args, source, meta, is_file, langs, get_audio, workdir, txt_path)
        with open(info_path, "w", encoding="utf-8") as f:
            json.dump(info, f, ensure_ascii=False, indent=2)
    if args.recheck:
        report = recheck(args, info, get_audio, workdir, txt_path)
        with open(info_path, "w", encoding="utf-8") as f:
            json.dump(info, f, ensure_ascii=False, indent=2)
        info["recheck"] = report
    if audio and not is_file and not args.keep_audio:
        os.remove(audio[0])
    if args.save:
        info["saved"] = save_markdown(info, txt_path, args.save, key, args.force)
    print(json.dumps(info, ensure_ascii=False, indent=2))


def transcribe(args, source: str, meta: dict, is_file: bool, langs: list[str],
               get_audio, workdir: str, txt_path: str) -> dict:
    info = {
        "source": source,
        "url": meta.get("webpage_url"),  # yt-dlp drops the ?si= and &t= of a shared link
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
             "--sub-format", "vtt/srt/best", "-o", os.path.join(workdir, "subs.%(ext)s"), "--", source])
        files = glob.glob(os.path.join(workdir, "subs.*"))
        if not files:
            fail(f"yt-dlp did not write the {lang} {kind}")
        cues = parse_cues(files[0], rolling=True)
        info.update(method=kind, language=lang)
    else:
        spoken = args.spoken_lang or (meta.get("language") or "").split("-")[0] or None
        srt, cmd, model = whisper(get_audio(), workdir, args.model, spoken)
        cues = parse_cues(srt)
        info.update(method="whisper", language=spoken or "auto-detected",
                    backend=cmd, model=model)

    write_lines(txt_path, cues)
    info.update(
        transcript=txt_path,
        lines=len(cues),
        characters=sum(len(t) for _, t in cues),
        warnings=find_loops(cues) if info["method"] == "whisper" else [],
    )
    return info


if __name__ == "__main__":
    main()

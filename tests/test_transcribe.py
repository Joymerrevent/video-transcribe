"""Unit tests for the pure functions in transcribe.py (no network, no Whisper)."""
import contextlib
import datetime
import decimal
import importlib.util
import io
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "skills", "video-transcribe", "scripts", "transcribe.py")
spec = importlib.util.spec_from_file_location("transcribe", SCRIPT)
transcribe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transcribe)


TMP = tempfile.TemporaryDirectory()


def tearDownModule():
    TMP.cleanup()


def write(text: str, suffix: str) -> str:
    fd, path = tempfile.mkstemp(suffix=suffix, dir=TMP.name)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def frontmatter(md: str) -> dict:
    """Read back the frontmatter, whose values build_markdown writes as JSON."""
    block = md.split("---\n")[1]
    return {k: json.loads(v) for k, v in (line.split(": ", 1) for line in block.splitlines())}


class ParseCuesTest(unittest.TestCase):
    def test_rolling_auto_captions_are_deduplicated(self):
        vtt = write(
            "WEBVTT\n\n"
            "00:00:01.000 --> 00:00:03.000\n"
            "hello <c>world</c>\n\n"
            "00:00:03.000 --> 00:00:05.000\n"
            "hello world\n"
            "how are you\n\n"
            "00:00:05.000 --> 00:00:07.000\n"
            "how are you\n"
            "fine &amp; you\n",
            ".vtt",
        )
        self.assertEqual(
            transcribe.parse_cues(vtt),
            [(1.0, "hello world"), (3.0, "how are you"), (5.0, "fine & you")],
        )

    def test_srt_multiline_cue_is_joined(self):
        srt = write(
            "1\n00:01:02,500 --> 00:01:04,000\nfirst line\nsecond line\n\n"
            "2\n01:00:00,000 --> 01:00:01,000\n日本語の\n字幕です\n",
            ".srt",
        )
        self.assertEqual(
            transcribe.parse_cues(srt),
            [(62.5, "first line second line"), (3600.0, "日本語の字幕です")],
        )


class FindLoopsTest(unittest.TestCase):
    def test_reports_long_runs_only(self):
        cues = [(float(i), "Yep.") for i in range(10)] + [(10.0, "done"), (11.0, "done")]
        warnings = transcribe.find_loops(cues)
        self.assertEqual(len(warnings), 1)
        self.assertIn("00:00:00-00:00:09", warnings[0])
        self.assertIn("x10", warnings[0])

    def test_short_runs_are_fine(self):
        self.assertEqual(transcribe.find_loops([(0.0, "ok")] * 7), [])


class PickSubtitleTest(unittest.TestCase):
    def test_preferred_manual_language_wins(self):
        meta = {"subtitles": {"fr": [], "en-US": []}, "automatic_captions": {"en-orig": []}}
        self.assertEqual(transcribe.pick_subtitle(meta, ["en"]), ("subtitles", "en-US"))

    def test_manual_in_spoken_language_is_fallback(self):
        meta = {"language": "ja", "subtitles": {"ja": []}, "automatic_captions": {}}
        self.assertEqual(transcribe.pick_subtitle(meta, ["en"]), ("subtitles", "ja"))

    def test_original_auto_captions_not_translations(self):
        meta = {"language": "ja", "subtitles": {},
                "automatic_captions": {"en": [], "ja-orig": [], "ja": []}}
        self.assertEqual(transcribe.pick_subtitle(meta, ["en"]), ("auto-captions", "ja-orig"))

    def test_auto_dubbed_video_uses_spoken_language_track(self):
        meta = {"language": "ja", "subtitles": {},
                "automatic_captions": {"en-US-orig": [], "ja-orig": [], "en": []}}
        self.assertEqual(transcribe.pick_subtitle(meta, ["en"]), ("auto-captions", "ja-orig"))

    def test_dub_only_original_track_is_not_used(self):
        meta = {"language": "ja", "subtitles": {}, "automatic_captions": {"en-US-orig": []}}
        self.assertIsNone(transcribe.pick_subtitle(meta, ["en"]))

    def test_unknown_spoken_language_uses_original_track(self):
        meta = {"subtitles": {}, "automatic_captions": {"en-orig": [], "fr": []}}
        self.assertEqual(transcribe.pick_subtitle(meta, ["en"]), ("auto-captions", "en-orig"))

    def test_translated_only_returns_none(self):
        meta = {"language": "ja", "subtitles": {"live_chat": []},
                "automatic_captions": {"en": [], "fr": []}}
        self.assertIsNone(transcribe.pick_subtitle(meta, ["en"]))

    def test_no_subtitles_at_all(self):
        self.assertIsNone(transcribe.pick_subtitle({}, ["en"]))


class BuildMarkdownTest(unittest.TestCase):
    def test_okf_frontmatter_and_chapters(self):
        info = {
            "source": "https://example.com/v", "title": 'Say "hi"', "uploader": "me",
            "duration": "00:01:00", "upload_date": "20260102", "method": "whisper",
            "language": "ja", "chapters": [{"start": "00:00:00", "title": "Intro"},
                                           {"start": "00:00:30", "title": "Main"}],
        }
        md = transcribe.build_markdown(info, ["[00:00:01] a", "[00:00:31] b"])
        front, body = md.split("\n---\n", 1)
        self.assertTrue(front.startswith("---\ntype: \"Reference\"\n"))
        self.assertIn('title: "Say \\"hi\\""', front)
        self.assertIn('x-video-transcribe-upload_date: "2026-01-02"', front)
        self.assertIn('tags: ["transcript"]', front)
        self.assertIn("\ngenerated: ", front)
        self.assertEqual(body, '\n# Say "hi"\n\n## Intro\n\n- [00:00:01] a\n\n## Main\n\n- [00:00:31] b\n')

    def test_missing_fields_are_left_out(self):
        md = transcribe.build_markdown({"title": "x.mp3", "method": "whisper"}, ["[00:00:00] hi"])
        self.assertNotIn("uploader", md)
        self.assertNotIn("null", md)
        self.assertTrue(md.endswith("# x.mp3\n\n- [00:00:00] hi\n"))

    def test_okf_v03_keys(self):
        info = {"source": "https://youtu.be/abc?si=x", "url": "https://www.youtube.com/watch?v=abc",
                "title": "t", "uploader": "me", "method": "subtitles", "language": "en"}
        fields = frontmatter(transcribe.build_markdown(info, ["[00:00:00] hi"]))
        self.assertEqual(fields["generated"]["by"], "video-transcribe/" + transcribe.VERSION)
        at = datetime.datetime.fromisoformat(fields["generated"]["at"])
        self.assertIsNotNone(at.tzinfo)  # OKF v0.3 §5: a date-time needs an offset
        self.assertEqual(fields["resource"], "https://www.youtube.com/watch?v=abc")
        self.assertEqual(fields["x-video-transcribe-method"], "subtitles")
        # Legacy and unprefixed keys are gone; every non-OKF key has the x- prefix.
        okf = {"type", "title", "description", "resource", "tags", "generated"}
        for key in fields.keys() - okf:
            self.assertTrue(key.startswith("x-video-transcribe-"), key)

    def test_local_file_resource_is_a_file_uri(self):
        path = os.path.join(TMP.name, "my talk.mp4")
        fields = frontmatter(transcribe.build_markdown({"source": path, "title": "my talk.mp4"}, []))
        self.assertEqual(fields["resource"], pathlib.Path(path).as_uri())
        self.assertTrue(fields["resource"].endswith("/my%20talk.mp4"))

    def test_resource_falls_back_to_source_url(self):
        # info.json cached by an older version has no "url".
        fields = frontmatter(transcribe.build_markdown({"source": "https://example.com/v"}, []))
        self.assertEqual(fields["resource"], "https://example.com/v")


class VersionTest(unittest.TestCase):
    def test_version_matches_latest_release_in_changelog(self):
        with open(os.path.join(HERE, "..", "CHANGELOG.md"), encoding="utf-8") as f:
            releases = re.findall(r"^## \[(\d+\.\d+\.\d+)\]", f.read(), re.M)
        if not releases:
            self.skipTest("no release in CHANGELOG.md yet")
        self.assertEqual(transcribe.VERSION, releases[0],
                         "bump VERSION in transcribe.py when adding a release to CHANGELOG.md")

    def test_version_option(self):
        out = subprocess.run([sys.executable, SCRIPT, "--version"], capture_output=True, text=True)
        self.assertEqual(out.returncode, 0)
        self.assertEqual(out.stdout, f"video-transcribe {transcribe.VERSION}\n")


class BackendsTest(unittest.TestCase):
    def test_audio_path_comes_after_end_of_options(self):
        for cmd, model, _, build in transcribe.BACKENDS:
            args = build("-x.mp3", model, "/tmp/out", "ja")
            self.assertEqual(args[0], cmd)
            self.assertEqual(args[-2:], ["--", "-x.mp3"], cmd)


class HelpersTest(unittest.TestCase):
    def test_time_conversions(self):
        self.assertEqual(transcribe.secs("01:02:03.500"), 3723.5)
        self.assertEqual(transcribe.secs("00:05,250"), 5.25)
        self.assertEqual(transcribe.hms(3723.9), "01:02:03")

    def test_slug(self):
        self.assertEqual(transcribe.slug("Youtube-abc/def?x"), "Youtube-abc-def-x")
        self.assertEqual(transcribe.slug("///"), "video")


def nums(*values) -> set:
    return {decimal.Decimal(str(v)) for v in values}


class NumbersTest(unittest.TestCase):
    def test_ways_of_writing_the_same_number_match(self):
        for text in ["9万7千", "9万7000", "97,000", "９万７千", "九万七千"]:
            self.assertEqual(transcribe.numbers(text), nums(97000), text)

    def test_kanji_and_mixed_numbers(self):
        self.assertEqual(transcribe.numbers("二〇二三年"), nums(2023))
        self.assertEqual(transcribe.numbers("二十三人"), nums(23))
        self.assertEqual(transcribe.numbers("三百五十万"), nums(3500000))
        self.assertEqual(transcribe.numbers("1億2000万"), nums(120000000))
        self.assertEqual(transcribe.numbers("1.5倍、5."), nums(1.5, 5))

    def test_commas(self):
        self.assertEqual(transcribe.numbers("1本4,500ドル"), nums(1, 4500))
        self.assertEqual(transcribe.numbers("1,234,567"), nums(1234567))
        # A comma that does not group thousands lists numbers: four or five.
        self.assertEqual(transcribe.numbers("4,5本"), nums(4, 5))
        self.assertEqual(transcribe.numbers("3,4年"), nums(3, 4))

    def test_kanji_only_numbers_are_matched_but_not_reported(self):
        self.assertEqual(transcribe.numbers("一緒に千葉へ"), nums(1, 1000))
        self.assertEqual(transcribe.numbers("一緒に千葉へ", digits_only=True), set())
        self.assertEqual(transcribe.numbers("2人と一緒", digits_only=True), nums(2))


class TranscriptLinesTest(unittest.TestCase):
    def test_round_trip_with_and_without_end(self):
        path = os.path.join(TMP.name, "lines.txt")
        transcribe.write_lines(path, [(1.5, "a"), (3600, "b")])
        self.assertEqual(transcribe.read_lines(path), [(1, None, "a"), (3600, None, "b")])
        transcribe.write_lines(path, [(1.5, 4.2, "a")])
        with open(path, encoding="utf-8") as f:
            self.assertEqual(f.read(), "[00:00:01-00:00:05] a\n")  # the end is rounded up
        self.assertEqual(transcribe.read_lines(path), [(1, 5, "a")])

    def test_vtt_end_time_with_cue_settings(self):
        vtt = write("WEBVTT\n\n00:00:01.000 --> 00:00:03.500 align:start position:0%\nhi\n", ".vtt")
        self.assertEqual(transcribe.parse_timed(vtt), [(1.0, 3.5, "hi")])


INFO = {"title": "t", "method": "whisper", "model": "turbo", "recheck": {"model": "large-v3"}}


def section(md: str, title: str) -> str:
    return md.split(f"## {title}", 1)[1].split("\n## ", 1)[0]


class BuildRecheckTest(unittest.TestCase):
    def test_numbers_that_differ_in_either_direction(self):
        first = [(10, None, "1本4,500ドル"), (40, None, "くじごじで働く"), (70, None, "9万7千ドル")]
        second = [(9, 12, "1本400から500ドル"), (39, 42, "9時5時で働く"), (68, 72, "9万7000ドル")]
        md, stats = transcribe.build_recheck(INFO, first, second)
        self.assertEqual(stats["numbers_differ"], 2)
        diff = section(md, "Numbers that differ")
        self.assertIn("### [00:00:10]\n\n- First: 1本4,500ドル\n- Second:\n  - [00:00:09] 1本400から500ドル\n"
                      "- Only in the first: 4500\n- Only in the second: 400, 500\n", diff)
        self.assertIn("### [00:00:40]", diff)
        self.assertIn("- Only in the second: 5, 9\n", diff)
        self.assertNotIn("[00:01:10]", diff)  # 9万7千 and 9万7000 are the same number

    def test_window_is_8_seconds_before_to_12_after(self):
        first = [(100, None, "5本")]
        for start, matched in [(93, True), (111, True), (88, False), (113, False)]:
            second = [(start, start + 1, "5本")]
            _, stats = transcribe.build_recheck(INFO, first, second)
            self.assertEqual(stats["not_covered"] == [], matched, start)

    def test_lines_without_a_second_transcript_are_not_covered_not_different(self):
        first = [(0, None, "1"), (100, None, "2本"), (110, None, "3本"), (200, None, "4")]
        second = [(0, 2, "1"), (199, 201, "4")]
        md, stats = transcribe.build_recheck(INFO, first, second)
        self.assertEqual(stats["numbers_differ"], 0)
        self.assertEqual(stats["not_covered"], ["00:01:40-00:01:50"])
        self.assertIn("- 00:01:40-00:01:50", section(md, "Not covered by the second transcript"))

    def test_side_by_side_nests_each_second_line_under_the_closest_first_line(self):
        first = [(0, None, "a"), (10, None, "b")]
        second = [(1, 3, "A"), (6, 8, "B"), (12, 14, "C")]
        md, _ = transcribe.build_recheck(INFO, first, second)
        self.assertTrue(md.endswith(
            "- [00:00:00] a\n  - [00:00:01] A\n- [00:00:10] b\n  - [00:00:06] B\n  - [00:00:12] C\n"))


FAKE_WHISPER = """\
import os, sys
args = sys.argv[1:]
out, model, audio = args[args.index("--output-dir") + 1], args[args.index("--model") + 1], args[-1]
with open(os.environ["FAKE_LOG"], "a") as f:
    f.write(f"whisper {model} {os.path.basename(audio)}\\n")
# The full run "drops" everything after 14 seconds; a clip has one line.
cues = [(0, 3, "clip line")] if audio.endswith("clip.wav") else [(0, 4, "first"), (10, 14, "1本400から500ドル")]
with open(os.path.join(out, "whisper.srt"), "w") as f:
    for i, (s, e, x) in enumerate(cues, 1):
        f.write(f"{i}\\n00:00:{s:02},000 --> 00:00:{e:02},000\\n{x}\\n\\n")
"""
FAKE_FFMPEG = """\
import os, sys
with open(os.environ["FAKE_LOG"], "a") as f:
    f.write("ffmpeg " + " ".join(sys.argv[1:]) + "\\n")
open(sys.argv[-1], "w").close()
"""


class RecheckTest(unittest.TestCase):
    """recheck() with fake mlx_whisper and ffmpeg commands on PATH."""

    def setUp(self):
        self.dir = tempfile.mkdtemp(dir=TMP.name)
        bindir = os.path.join(self.dir, "bin")
        os.mkdir(bindir)
        for name, body in [("mlx_whisper", FAKE_WHISPER), ("ffmpeg", FAKE_FFMPEG)]:
            path = os.path.join(bindir, name)
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"#!{sys.executable}\n{body}")
            os.chmod(path, 0o755)
        self.log = os.path.join(self.dir, "calls.log")
        self.env = dict(os.environ)
        os.environ.update(PATH=bindir + os.pathsep + os.environ["PATH"], FAKE_LOG=self.log)
        self.txt = os.path.join(self.dir, "transcript.txt")
        transcribe.write_lines(self.txt, [(0, "first"), (10, "1本4,500ドル"), (60, "last line")])

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.env)

    def calls(self) -> list[str]:
        if not os.path.exists(self.log):
            return []
        with open(self.log, encoding="utf-8") as f:
            return f.read().splitlines()

    def recheck(self, info: dict, get_audio=lambda: "/media/audio.webm") -> dict:
        args = types.SimpleNamespace(force=False, spoken_lang=None)
        with contextlib.redirect_stderr(io.StringIO()):
            return transcribe.recheck(args, info, get_audio, self.dir, self.txt)

    def test_second_model_fills_gaps_and_is_cached(self):
        info = {"title": "t", "method": "whisper", "language": "ja", "model": "turbo"}
        report = self.recheck(info)
        second = "mlx-community/whisper-large-v3-mlx"
        self.assertEqual(self.calls(), [
            f"whisper {second} audio.webm",
            # The line at 60 s has nothing around it, so 55-75 s is cut out and done again.
            "ffmpeg -nostdin -loglevel error -y -ss 55 -to 75 -i /media/audio.webm -ac 1 -ar 16000 "
            + os.path.join(self.dir, "recheck", "clip.wav"),
            f"whisper {second} clip.wav",
        ])
        with open(os.path.join(self.dir, "recheck.txt"), encoding="utf-8") as f:
            self.assertEqual(f.read(), "[00:00:00-00:00:04] first\n"
                                       "[00:00:10-00:00:14] 1本400から500ドル\n"
                                       "[00:00:55-00:00:58] clip line\n")
        self.assertFalse(os.path.exists(os.path.join(self.dir, "recheck", "clip.wav")))
        self.assertEqual(report["numbers_differ"], 1)
        self.assertEqual(report["not_covered"], [])
        self.assertEqual(info["recheck"], {"backend": "mlx_whisper", "model": second,
                                           "transcript": os.path.join(self.dir, "recheck.txt")})

        os.remove(self.log)

        def no_audio():
            raise AssertionError("the cached second transcript needs no audio")
        self.assertEqual(self.recheck(info, no_audio)["numbers_differ"], 1)
        self.assertEqual(self.calls(), [])

    def test_human_subtitles_are_not_rechecked(self):
        with self.assertRaises(SystemExit):
            self.recheck({"method": "subtitles", "language": "en"})
        self.assertEqual(self.calls(), [])

    def test_same_model_twice_is_refused(self):
        with self.assertRaises(SystemExit):
            self.recheck({"method": "whisper", "model": "mlx-community/whisper-large-v3-mlx"})
        self.assertEqual(self.calls(), [])


if __name__ == "__main__":
    unittest.main()

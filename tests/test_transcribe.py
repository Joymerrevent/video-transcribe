"""Unit tests for the pure functions in transcribe.py (no network, no Whisper)."""
import importlib.util
import os
import tempfile
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
        self.assertTrue(front.startswith("---\ntype: \"reference\"\n"))
        self.assertIn('title: "Say \\"hi\\""', front)
        self.assertIn('upload_date: "2026-01-02"', front)
        self.assertIn('tags: ["transcript"]', front)
        self.assertIn("\ntimestamp: ", front)
        self.assertEqual(body, '\n# Say "hi"\n\n## Intro\n\n- [00:00:01] a\n\n## Main\n\n- [00:00:31] b\n')

    def test_missing_fields_are_left_out(self):
        md = transcribe.build_markdown({"title": "x.mp3", "method": "whisper"}, ["[00:00:00] hi"])
        self.assertNotIn("uploader", md)
        self.assertNotIn("null", md)
        self.assertTrue(md.endswith("# x.mp3\n\n- [00:00:00] hi\n"))


class BackendsTest(unittest.TestCase):
    def test_audio_path_comes_after_end_of_options(self):
        for cmd, model, build in transcribe.BACKENDS:
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


if __name__ == "__main__":
    unittest.main()

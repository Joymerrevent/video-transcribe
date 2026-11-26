# Changelog

All notable changes to this project are documented in this file.
The format is based on [Keep a Changelog][keepachangelog], and this project follows [Semantic Versioning][semver].

## [Unreleased]

## [0.1.0] - 2026-11-26

### Added

- `video-transcribe` skill: transcribes videos from YouTube and any other site yt-dlp supports, and local audio/video files.
- Uses the platform's subtitles when available and falls back to local Whisper (mlx-whisper, whisper-ctranslate2, or openai-whisper).
- For auto-dubbed videos, uses the captions and audio in the original language.
- Detects Whisper repetition loops and reports them as warnings.
- Caches transcripts in `~/.cache/video-transcribe/`.
- `--save <dir>` writes the transcript as Markdown with OKF (Open Knowledge Format) v0.3 frontmatter, split by chapter.
- `--recheck` transcribes the audio again with a larger Whisper model and writes `recheck.md`, which compares the two transcripts to find misheard words. The skill describes how the agent decides and records each fix.
- `--version` prints the version.

[keepachangelog]: https://keepachangelog.com/en/1.1.0/
[semver]: https://semver.org/
[Unreleased]: https://github.com/Joymerrevent/video-transcribe/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Joymerrevent/video-transcribe/releases/tag/v0.1.0

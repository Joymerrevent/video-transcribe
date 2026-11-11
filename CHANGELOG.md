# Changelog

All notable changes to this project are documented in this file.
The format is based on [Keep a Changelog][keepachangelog].

## [Unreleased]

### Added

- `video-transcribe` skill: transcribes videos from YouTube and any other site yt-dlp supports, and local audio/video files.
- Uses the platform's subtitles when available and falls back to local Whisper (mlx-whisper, whisper-ctranslate2, or openai-whisper).
- Detects Whisper repetition loops and reports them as warnings.
- Caches transcripts in `~/.cache/video-transcribe/`.
- `--save <dir>` writes the transcript as Markdown with OKF (Open Knowledge Format) frontmatter, split by chapter.

[keepachangelog]: https://keepachangelog.com/en/1.1.0/
[Unreleased]: https://github.com/Joymerrevent/video-transcribe/commits/main

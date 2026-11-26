# Changelog

All notable changes to this project are documented in this file.
The format is based on [Keep a Changelog][keepachangelog], and this project follows [Semantic Versioning][semver].

## [Unreleased]

## [0.4.0] - 2026-11-27

### Changed

- After transcribing, the agent no longer reads the transcript file, so the tokens it uses for a transcription no longer grow with the video's length. It reads the file only when you ask about the video, and decides then whether to read the whole file or only the parts it needs. Its reply after transcribing gives only the title, the method, where the transcript is, and any warnings.
- The agent runs `--recheck` and fixes the transcript only when you ask for it, because fixing the transcript means reading it, which uses AI tokens.

## [0.3.0] - 2026-11-26

### Changed

- The `--save` frontmatter always writes every OKF key that applies to any type: `null` for `verified`, `sources`, `stale_after`, and `superseded_by`, and `status: "stable"`. Keys outside OKF are still written only when they have a value.
- In the `--save` frontmatter, `x-video-transcribe-upload_date` is renamed `x-video-transcribe-upload-date`, like the other `x-video-transcribe-*` keys. Files saved by earlier versions keep the old name.

## [0.2.0] - 2026-11-26

### Added

- Can be installed as a Claude Code plugin: `/plugin install video-transcribe --marketplace Joymerrevent/video-transcribe`.

### Changed

- The skill moved from `skills/video-transcribe/` to `plugin/skills/video-transcribe/`. Installing with `npx skills` works as before. If you run the script from a clone of this repository, use the new path.

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
[Unreleased]: https://github.com/Joymerrevent/video-transcribe/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/Joymerrevent/video-transcribe/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/Joymerrevent/video-transcribe/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/Joymerrevent/video-transcribe/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/Joymerrevent/video-transcribe/releases/tag/v0.1.0

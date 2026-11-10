# video-transcribe

An agent skill that turns a video into a timestamped text transcript. [日本語の説明は下にあります。][ja]

- Works with YouTube and any other site [yt-dlp][yt-dlp] supports, plus local audio and video files.
- Uses the platform's subtitles when they exist. When they don't, it downloads the audio only and transcribes it locally with Whisper.
- Nothing is sent to an external API. Only yt-dlp and the one-time Whisper model download use the network.
- One Python script with no Python dependencies. It does not summarize; the agent writes summaries or answers from the transcript in whatever form you ask for.

## Install

```bash
npx skills add Joymerrevent/video-transcribe
```

Then install the tools the script calls:

```bash
brew install yt-dlp ffmpeg
uv tool install mlx-whisper          # Apple Silicon
# uv tool install whisper-ctranslate2  # Linux, Intel Mac, Windows
```

A Whisper CLI is only needed for videos without subtitles and for local files. The first Whisper run downloads the model (about 1.5 GB).

## Use

Ask your agent, for example:

- "Transcribe https://www.youtube.com/watch?v=..."
- "What does this video say about pricing? https://vimeo.com/..."
- "Transcribe ~/Movies/meeting.mp4"

The agent runs `scripts/transcribe.py` and reads the transcript. You can also run the script yourself:

```bash
python3 skills/video-transcribe/scripts/transcribe.py "<url-or-file>" [--lang ja,en] [--whisper]
```

Run it with `--help` for all options. Transcripts are cached in `~/.cache/video-transcribe/`.

## How subtitles are chosen

1. Human-made subtitles in a preferred language (`--lang`, default `ja,en`)
2. Human-made subtitles in the spoken language
3. Auto-generated captions in the spoken language
4. Otherwise, local Whisper on the audio

Auto-translated captions are never used, because they are a machine translation of what was said. Auto-generated captions often lack punctuation; pass `--whisper` (or ask the agent to use Whisper) for cleaner text.

## Credits

The approach is based on the `watch-video` skill in [coreyhaines31/makerskills][makerskills] (MIT), reduced to transcription only.

## License

[MIT][license]

---

## 日本語

動画を、時刻付きの文字起こしに変える AI エージェント用のスキルです。

- YouTube のほか、[yt-dlp][yt-dlp] が対応しているサイトの動画と、手元の音声・動画ファイルを文字に起こせます。
- 動画に字幕があれば字幕を使います。字幕がなければ音声だけをダウンロードし、手元の PC で Whisper を使って文字に起こします。
- 音声や文字起こしを外部の API に送りません。ネットワークを使うのは、yt-dlp と、初回の Whisper のモデルのダウンロードだけです。
- 中身は Python のスクリプト 1 本で、追加の Python パッケージは要りません。要約はしません。要約や質問への答えは、文字起こしをもとにエージェントが頼まれた形で書きます。

### インストール

```bash
npx skills add Joymerrevent/video-transcribe
```

スクリプトが使うツールも入れます。

```bash
brew install yt-dlp ffmpeg
uv tool install mlx-whisper          # Apple Silicon の Mac
# uv tool install whisper-ctranslate2  # Linux・Intel の Mac・Windows
```

Whisper は、字幕のない動画と手元のファイルを文字に起こすときだけ使います。初めて使うときに、モデル（約 1.5 GB）をダウンロードします。

### 使い方

エージェントに次のように頼みます。

- 「https://www.youtube.com/watch?v=... を文字起こしして」
- 「この動画で料金について何と言っている？ https://vimeo.com/...」
- 「~/Movies/meeting.mp4 を文字起こしして」

エージェントは `scripts/transcribe.py` を実行し、できた文字起こしを読みます。スクリプトを直接実行することもできます。

```bash
python3 skills/video-transcribe/scripts/transcribe.py "<URL かファイル>" [--lang ja,en] [--whisper]
```

すべてのオプションは `--help` で確かめられます。文字起こしは `~/.cache/video-transcribe/` に保存され、同じ動画をもう一度頼むとすぐに返します。

### 字幕の選び方

1. 人が作った字幕のうち、優先する言語のもの（`--lang`。初期値は `ja,en`）
2. 人が作った字幕のうち、話している言語のもの
3. 自動生成の字幕のうち、話している言語のもの
4. どれもなければ、音声を手元の Whisper で文字に起こす

自動翻訳の字幕は使いません。自動翻訳の字幕は、話した内容を機械で翻訳したもので、文字起こしではないためです。自動生成の字幕は句読点がなく読みにくいことが多いので、きれいな文章にしたいときは `--whisper` を付けて（またはエージェントに「Whisper で」と頼んで）ください。

### クレジット

[coreyhaines31/makerskills][makerskills]（MIT ライセンス）の `watch-video` スキルをもとに、文字起こしの機能だけに絞って作りました。

### ライセンス

[MIT][license]

[ja]: #日本語
[yt-dlp]: https://github.com/yt-dlp/yt-dlp
[makerskills]: https://github.com/coreyhaines31/makerskills
[license]: LICENSE

# video-transcribe

An agent skill that turns a video into a timestamped text transcript. [日本語の説明は下にあります。][ja]

- Works with YouTube and any other site [yt-dlp][yt-dlp] supports, plus local audio and video files.
- Uses the platform's subtitles when they exist. When they don't, it downloads the audio only and transcribes it locally with Whisper.
- The transcription itself uses no AI tokens. The agent only runs the script and reads its short report: the title, how the video was transcribed, where the transcript is, and any warnings. The agent reads the transcript only when you ask about the video.
- Transcription accuracy does not depend on the AI model the agent uses. It comes from the video's subtitles or from Whisper, a speech recognition model that runs on your computer.
- The script sends nothing to an external API. Only yt-dlp and the one-time Whisper model download use the network.
- One Python script with no Python dependencies. It does not summarize; when you ask about the video, the agent reads the transcript and answers in whatever form you ask for.

## Install

```bash
npx skills add Joymerrevent/video-transcribe
```

This installs the latest code on `main`. To install a released version, add its tag. The versions are listed on the [Releases][releases] page.

```bash
npx skills add Joymerrevent/video-transcribe@<tag> --skill video-transcribe
```

In Claude Code 2.1.275 or later, you can install it as a plugin instead:

```text
/plugin install video-transcribe --marketplace Joymerrevent/video-transcribe
```

To get a new version later, run `claude plugin update video-transcribe@video-transcribe`. Use one of these ways, not both: each way installs its own copy of the skill.

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

The agent runs `scripts/transcribe.py` and tells you the title, how the video was transcribed, where the transcript is, and any warnings. It does not read the transcript at that point. When you ask about the video, as in the second example, the agent reads the transcript (the whole file, or only the parts it needs) and answers. You can also run the script yourself:

```bash
python3 plugin/skills/video-transcribe/scripts/transcribe.py "<url-or-file>" [--lang ja,en] [--whisper]
```

Run it with `--help` for all options and `--version` for the version. Transcripts are cached in `~/.cache/video-transcribe/`. The script prints only a short JSON report, never the whole transcript.

To keep the transcript in your project, add `--save <dir>` (or tell the agent where to save it). It writes `<dir>/<site>-<id>.md`, a Markdown file with [OKF][okf] v0.3 frontmatter (`type: Reference`, title, the video URL as `resource`, and so on; every OKF key is written, with `null` where there is no value) and the timestamped lines, split by chapter when the video has chapters. An existing file is kept unless you add `--force`.

Whisper and auto-generated captions can mishear names and numbers. To check them, add `--recheck` (or ask the agent to check the transcript). The script transcribes the audio again with a larger Whisper model and writes `recheck.md`, which puts the two transcripts side by side and lists the lines where their numbers differ. The agent then fixes the spots it can decide from the two transcripts and the context, and records each fix. The agent does this only when you ask for it: to make the fixes, it reads `recheck.md` and the transcript, so this step uses AI tokens, and how good the fixes are depends on the agent's AI model. The larger model is downloaded on first use (about 3 GB). Transcripts from human-made subtitles are not rechecked.

## How subtitles are chosen

1. Human-made subtitles in a preferred language (`--lang`, default `en`)
2. Human-made subtitles in the spoken language
3. Auto-generated captions in the spoken language
4. Otherwise, local Whisper on the audio

Auto-translated captions are never used, because they are a machine translation of what was said. Auto-generated captions often lack punctuation; pass `--whisper` (or ask the agent to use Whisper) for cleaner text.

## Security

To report a security issue, follow [SECURITY.md][security] instead of opening a public issue.

## Credits

The approach is based on the `watch-video` skill in [coreyhaines31/makerskills][makerskills] (MIT), reduced to transcription only.

## License

[MIT][license]

---

## 日本語

動画を、時刻付きの文字起こしに変える AI エージェント用のスキルです。

- YouTube のほか、[yt-dlp][yt-dlp] が対応しているサイトの動画と、手元の音声・動画ファイルを文字に起こせます。
- 動画に字幕があれば字幕を使います。字幕がなければ音声だけをダウンロードし、手元の PC で Whisper を使って文字に起こします。
- 文字起こしの処理そのものでは、AI のトークンを使いません。エージェントは、スクリプトを実行して短い報告（タイトル・文字起こしの方法・文字起こしの保存場所・警告）を読むだけです。エージェントが文字起こしを読むのは、動画について質問したときだけです。
- 文字起こしの精度は、エージェントが使っている AI のモデルに左右されません。精度は、動画の字幕か、手元の PC で動く音声認識のモデル（Whisper）で決まります。
- スクリプトは、音声や文字起こしを外部の API に送りません。ネットワークを使うのは、yt-dlp と、初回の Whisper のモデルのダウンロードだけです。
- 中身は Python のスクリプト 1 本で、追加の Python パッケージは要りません。要約はしません。動画について質問すると、エージェントが文字起こしを読み、頼まれた形で答えます。

### インストール

```bash
npx skills add Joymerrevent/video-transcribe
```

この方法では、`main` の最新のコードが入ります。リリースした版を入れるときは、版のタグを付けます。版の一覧は [Releases][releases] のページにあります。

```bash
npx skills add Joymerrevent/video-transcribe@<タグ> --skill video-transcribe
```

Claude Code 2.1.275 以降では、代わりにプラグインとして入れることもできます。

```text
/plugin install video-transcribe --marketplace Joymerrevent/video-transcribe
```

新しい版が出たら、`claude plugin update video-transcribe@video-transcribe` で更新します。入れ方はどちらか 1 つにしてください。両方で入れると、同じスキルが 2 つ入ります。

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

エージェントは `scripts/transcribe.py` を実行し、タイトル・文字起こしの方法・文字起こしの保存場所・警告を伝えます。この時点では、文字起こしを読みません。2 つめの例のように動画について質問すると、エージェントが文字起こしを読み（全部を読むか、必要な部分だけを読むかはエージェントが決めます）、答えます。スクリプトを直接実行することもできます。

```bash
python3 plugin/skills/video-transcribe/scripts/transcribe.py "<URL かファイル>" [--lang ja,en] [--whisper]
```

すべてのオプションは `--help` で、版は `--version` で確かめられます。文字起こしは `~/.cache/video-transcribe/` に保存され、同じ動画をもう一度頼むとすぐに返します。スクリプトが画面に出すのは短い報告（JSON）だけで、文字起こしの全文は出しません。

文字起こしをプロジェクトに残したいときは、`--save <フォルダ>` を付けます（エージェントに保存先を伝えても同じです）。`<フォルダ>/<サイト>-<ID>.md` に、[OKF][okf] v0.3 のフロントマター（`type: Reference`・タイトル・`resource` に入れた動画の URL など。OKF の項目は、値が無ければ `null` にして全部書きます）と時刻付きの文字起こしを書いた Markdown を作ります。動画に章があれば、章ごとに見出しで区切ります。同じ名前のファイルがあるときは上書きしません。上書きするときは `--force` を付けます。

Whisper と自動生成の字幕は、人名や数字を聞き違えることがあります。確かめたいときは `--recheck` を付けます（エージェントに「聞き違いを確かめて」と頼んでも同じです）。スクリプトは大きいほうの Whisper のモデルで音声をもう一度文字に起こし、2 つの文字起こしを並べた `recheck.md` を作ります。`recheck.md` には、数字が食い違う行の一覧も入ります。エージェントは、2 つの文字起こしと前後の文脈で決められる箇所を直し、直したことを記録します。エージェントが直すのは、頼まれたときだけです。直すときは `recheck.md` と文字起こしを読むので、AI のトークンを使います。直した結果の良し悪しは、エージェントが使っている AI のモデルに左右されます。大きいほうのモデルは、初めて使うときにダウンロードします（約 3 GB）。人が作った字幕の文字起こしは、確かめる対象にしません。

### 字幕の選び方

1. 人が作った字幕のうち、優先する言語のもの（`--lang`。初期値は `en`）
2. 人が作った字幕のうち、話している言語のもの
3. 自動生成の字幕のうち、話している言語のもの
4. どれもなければ、音声を手元の Whisper で文字に起こす

自動翻訳の字幕は使いません。自動翻訳の字幕は、話した内容を機械で翻訳したもので、文字起こしではないためです。自動生成の字幕は句読点がなく読みにくいことが多いので、きれいな文章にしたいときは `--whisper` を付けて（またはエージェントに「Whisper で」と頼んで）ください。

### セキュリティ

セキュリティの問題は、公開の Issue ではなく、[SECURITY.md][security] の手順で報告してください。

### クレジット

[coreyhaines31/makerskills][makerskills]（MIT ライセンス）の `watch-video` スキルをもとに、文字起こしの機能だけに絞って作りました。

### ライセンス

[MIT][license]

[ja]: #日本語
[yt-dlp]: https://github.com/yt-dlp/yt-dlp
[makerskills]: https://github.com/coreyhaines31/makerskills
[license]: LICENSE
[okf]: https://github.com/open-knowledge-format/open-knowledge-format/blob/main/SPEC.md
[security]: SECURITY.md
[releases]: https://github.com/Joymerrevent/video-transcribe/releases

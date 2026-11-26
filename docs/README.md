# 開発者向けの案内

このスキルを開発・保守するための案内です。スキルの入れ方と使い方は、リポジトリのトップの [README][readme] にあります。

`docs/` の資料は開発者向けで、コミットメッセージ・Issue・プルリクエストと同じく日本語で書きます。

## ファイル

| パス | 中身 |
|---|---|
| `skills/video-transcribe/` | 利用者が入れるスキル |
| `skills/video-transcribe/SKILL.md` | エージェントへの指示 |
| `skills/video-transcribe/scripts/transcribe.py` | エージェントが実行するスクリプト。Python の標準ライブラリだけを使う |
| `tests/` | 単体テスト。ネットワーク・yt-dlp・Whisper は要らない（偽のコマンドで代わりにする） |
| `.claude-plugin/` | Claude Code のプラグインの設定（`plugin.json`）と、このリポジトリをマーケットプレイスにする設定（`marketplace.json`） |
| `CHANGELOG.md` | リリースごとの変更 |
| `docs/` | この案内のような、開発者向けの資料 |

## テスト

```bash
python3 -m unittest discover -s tests -v
```

CI でも、対応する中でいちばん古い Python と、今の Python で同じテストを実行します。Python の版は [ci.yml][ci] にあります。

`.claude-plugin/` を変えたら、`claude plugin validate .` で確かめます（CI には Claude Code が無いので、手元で行います）。アイコンを置くまでは、アイコンが無いという警告が出ます。アイコンは、Anthropic のディレクトリに初めて保存・申し込みをしたときだけ一覧に使われ、あとから変えられないので、申し込みの前に決めます。

## 変更の記録

利用者に見える変更（オプション・出力・スキルの指示）をするプルリクエストでは、同じプルリクエストの中で [CHANGELOG.md][changelog] の `[Unreleased]` に項目を足します。

## リリース

[リリースのしかた][releasing]に従います。

## CONTRIBUTING.md を作る時期

今は CONTRIBUTING.md を置いていません。これまでの Issue とプルリクエストは、すべて保守する人が作ったものだからです。次のどれか 1 つに当てはまったら作ります。

1. 保守する人と bot（Dependabot など）以外の人がプルリクエストを出した、または出したいと言ってきた。
2. 外からの Issue やプルリクエストに、同じ案内を 2 回した（「テストを通してください」「CHANGELOG に書いてください」など）。
3. 貢献を呼びかけることにした（告知する、`good first issue` のラベルを使う、など）。
4. 外の人だけに求める決まりが要るようになった（貢献したコードの権利の扱い、行動規範、誰がどうマージするか）。

GitHub は、リポジトリの直下・`docs/`・`.github/` のどこに置いた CONTRIBUTING.md も見つけます。Issue の出し方、プルリクエストの手順（ブランチ・テスト・CHANGELOG・コミットメッセージ）、マージを誰が決めるかを書きます。細かい手順は、書き写さずにこの案内を指します。

外の人は日本語を読めないかもしれないので、CONTRIBUTING.md をどの言葉で書くか（英語だけか、英語と日本語の両方か）も、作るときに決めます。

[readme]: ../README.md
[ci]: ../.github/workflows/ci.yml
[changelog]: ../CHANGELOG.md
[releasing]: releasing.md

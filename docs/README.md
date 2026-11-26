# Developer guide

Notes for developing and maintaining this skill. The documents in `docs/` are for developers. How to install and use the skill is in the [README][readme] at the top of the repository. [日本語の説明は下にあります。][ja]

## Files

| Path | What it is |
|---|---|
| `skills/video-transcribe/` | The skill that users install |
| `skills/video-transcribe/SKILL.md` | Instructions for the agent |
| `skills/video-transcribe/scripts/transcribe.py` | The script that the agent runs. It uses the Python standard library only |
| `tests/` | Unit tests. They need no network, yt-dlp, or Whisper: fake commands stand in for those |
| `CHANGELOG.md` | The changes in each release |
| `docs/` | Documents for developers, such as this one |

## Tests

```bash
python3 -m unittest discover -s tests -v
```

CI runs the same tests on the oldest supported Python and on the current one. The versions are in [ci.yml][ci].

## Recording changes

When a pull request changes something that users see (options, output, or the skill's instructions), add an entry under `[Unreleased]` in [CHANGELOG.md][changelog] in the same pull request.

## Releasing

Follow [releasing.md][releasing].

## When to add CONTRIBUTING.md

There is no CONTRIBUTING.md yet, because so far only the maintainer has opened issues and pull requests. Add one when any of these happens:

1. Someone other than the maintainer and bots (such as Dependabot) opens a pull request, or says they want to.
2. You have given outside issues or pull requests the same guidance twice, for example "run the tests" or "add a CHANGELOG entry".
3. You decide to invite contributions, for example with an announcement or `good first issue` labels.
4. You need rules for outside contributors only: the rights to contributed code, a code of conduct, or who merges and how.

GitHub finds CONTRIBUTING.md in the repository root, in `docs/`, or in `.github/`. Explain how to open an issue, the steps for a pull request (branch, tests, CHANGELOG, commit messages), and who decides to merge. For the details, link to this guide instead of copying it.

---

## 日本語

このスキルを開発・保守するための案内です。`docs/` の資料は開発者向けです。スキルの入れ方と使い方は、リポジトリのトップの [README][readme] にあります。

### ファイル

| パス | 中身 |
|---|---|
| `skills/video-transcribe/` | 利用者が入れるスキル |
| `skills/video-transcribe/SKILL.md` | エージェントへの指示 |
| `skills/video-transcribe/scripts/transcribe.py` | エージェントが実行するスクリプト。Python の標準ライブラリだけを使う |
| `tests/` | 単体テスト。ネットワーク・yt-dlp・Whisper は要らない（偽のコマンドで代わりにする） |
| `CHANGELOG.md` | リリースごとの変更 |
| `docs/` | この案内のような、開発者向けの資料 |

### テスト

```bash
python3 -m unittest discover -s tests -v
```

CI でも、対応する中でいちばん古い Python と、今の Python で同じテストを実行します。Python の版は [ci.yml][ci] にあります。

### 変更の記録

利用者に見える変更（オプション・出力・スキルの指示）をするプルリクエストでは、同じプルリクエストの中で [CHANGELOG.md][changelog] の `[Unreleased]` に項目を足します。

### リリース

[releasing.md][releasing] の手順に従います。

### CONTRIBUTING.md を作る時期

今は CONTRIBUTING.md を置いていません。これまでの Issue とプルリクエストは、すべて保守する人が作ったものだからです。次のどれか 1 つに当てはまったら作ります。

1. 保守する人と bot（Dependabot など）以外の人がプルリクエストを出した、または出したいと言ってきた。
2. 外からの Issue やプルリクエストに、同じ案内を 2 回した（「テストを通してください」「CHANGELOG に書いてください」など）。
3. 貢献を呼びかけることにした（告知する、`good first issue` のラベルを使う、など）。
4. 外の人だけに求める決まりが要るようになった（貢献したコードの権利の扱い、行動規範、誰がどうマージするか）。

GitHub は、リポジトリの直下・`docs/`・`.github/` のどこに置いた CONTRIBUTING.md も見つけます。Issue の出し方、プルリクエストの手順（ブランチ・テスト・CHANGELOG・コミットメッセージ）、マージを誰が決めるかを書きます。細かい手順は、書き写さずにこの案内を指します。

[readme]: ../README.md
[ja]: #日本語
[ci]: ../.github/workflows/ci.yml
[changelog]: ../CHANGELOG.md
[releasing]: releasing.md

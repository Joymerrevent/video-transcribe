# リリースのしかた

このスキルの新しい版を公開する手順です。

版の番号は[セマンティック バージョニング][semver]に従い、リリースごとに `vX.Y.Z` のタグを付けます。利用者はタグを指定してリリースを入れられるので、一度付けたタグは動かさず、使い回しません。

## 手順

1. 次の変更をするプルリクエストを作ります。
   - [CHANGELOG.md][changelog] の `[Unreleased]` の項目を、新しい `## [X.Y.Z] - YYYY-MM-DD` の節に移し、ファイルの末尾のリンクを直す
   - `plugin/skills/video-transcribe/scripts/transcribe.py` の `VERSION` と、`plugin/.claude-plugin/plugin.json` の `version` を同じ番号にする。番号が食い違うと、テストが落ちる。プラグインの利用者は、`plugin.json` の `version` が上がったときに新しい版を受け取る
2. プルリクエストをマージし、`main` の CI が通るのを待ちます。
3. マージのコミットに署名付きのタグを付け、タグを push します。CHANGELOG の節の日付から日がずれたときは、先にプルリクエストで日付を直します。

   ```bash
   git fetch origin
   git tag -s vX.Y.Z <マージのコミット> -m "vX.Y.Z"
   git push origin vX.Y.Z
   ```

4. タグから GitHub のリリースを公開します。リリースノートには、CHANGELOG の新しい節と、その版を入れるコマンド（`npx skills add Joymerrevent/video-transcribe@vX.Y.Z --skill video-transcribe`）を載せた「Install this version」を書きます。リリースノートは利用者が読むので、CHANGELOG と同じく英語で書きます。

   ```bash
   gh release create vX.Y.Z --verify-tag --title vX.Y.Z --notes-file <ノートのファイル>
   ```

5. 公開したリリースを確かめます。
   - GitHub でタグが **Verified**（署名を確認済み）になっている
   - タグの中身のスクリプトが、`--version` で新しい版を出す
   - CHANGELOG.md にある新しい版へのリンクが開ける

[semver]: https://semver.org/lang/ja/
[changelog]: ../CHANGELOG.md

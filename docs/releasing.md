# Releasing

How to publish a new version of this skill. [日本語の説明は下にあります。][ja]

Versions follow [Semantic Versioning][semver], and each release has a tag named `vX.Y.Z`. Users can install a release by its tag, so a tag must never be moved or reused.

## Steps

1. Open a pull request that:
   - moves the entries under `[Unreleased]` in [CHANGELOG.md][changelog] into a new `## [X.Y.Z] - YYYY-MM-DD` section, and updates the links at the bottom of the file;
   - sets `VERSION` in `skills/video-transcribe/scripts/transcribe.py` to the same number. The tests fail if the two numbers differ.
2. Merge the pull request, and wait for CI to pass on `main`.
3. Tag the merge commit with a signed tag, and push the tag. If the date is no longer the one in the CHANGELOG section, fix the date in a pull request first.

   ```bash
   git fetch origin
   git tag -s vX.Y.Z <merge-commit> -m "vX.Y.Z"
   git push origin vX.Y.Z
   ```

4. Publish a GitHub release from the tag. The release notes are the new CHANGELOG section, followed by an "Install this version" part that shows `npx skills add Joymerrevent/video-transcribe@vX.Y.Z --skill video-transcribe`.

   ```bash
   gh release create vX.Y.Z --verify-tag --title vX.Y.Z --notes-file <notes-file>
   ```

5. Check the release:
   - GitHub shows the tag as **Verified**.
   - The script at the tag prints the new version with `--version`.
   - The links in CHANGELOG.md to the new version open.

---

## 日本語

このスキルの新しい版を公開する手順です。

版の番号は[セマンティック バージョニング][semver-ja]に従い、リリースごとに `vX.Y.Z` のタグを付けます。利用者はタグを指定してリリースを入れられるので、一度付けたタグは動かさず、使い回しません。

### 手順

1. 次の変更をするプルリクエストを作ります。
   - [CHANGELOG.md][changelog] の `[Unreleased]` の項目を、新しい `## [X.Y.Z] - YYYY-MM-DD` の節に移し、ファイルの末尾のリンクを直す
   - `skills/video-transcribe/scripts/transcribe.py` の `VERSION` を同じ番号にする。2 つの番号が食い違うと、テストが落ちる
2. プルリクエストをマージし、`main` の CI が通るのを待ちます。
3. マージのコミットに署名付きのタグを付け、タグを push します。CHANGELOG の節の日付から日がずれたときは、先にプルリクエストで日付を直します。

   ```bash
   git fetch origin
   git tag -s vX.Y.Z <マージのコミット> -m "vX.Y.Z"
   git push origin vX.Y.Z
   ```

4. タグから GitHub のリリースを公開します。リリースノートには、CHANGELOG の新しい節と、その版を入れるコマンド（`npx skills add Joymerrevent/video-transcribe@vX.Y.Z --skill video-transcribe`）を載せた「Install this version」を書きます。

   ```bash
   gh release create vX.Y.Z --verify-tag --title vX.Y.Z --notes-file <ノートのファイル>
   ```

5. 公開したリリースを確かめます。
   - GitHub でタグが **Verified**（署名を確認済み）になっている
   - タグの中身のスクリプトが、`--version` で新しい版を出す
   - CHANGELOG.md にある新しい版へのリンクが開ける

[ja]: #日本語
[semver]: https://semver.org/
[semver-ja]: https://semver.org/lang/ja/
[changelog]: ../CHANGELOG.md

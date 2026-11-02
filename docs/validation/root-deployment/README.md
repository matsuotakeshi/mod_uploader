# リビジョン6の検証ログ

2026-11-02の隔離FreeBSD検証です。[検証報告](../../ROOT-VALIDATION-ja.md)と[設定手順](../../ROOT-DEPLOYMENT-ja.md)を参照してください。本番データや実際の認証情報、テスト用秘密鍵・セッションは収録しません。ログの作業ディレクトリ名は`<test-dir>`に置換しています。

- `environment.log`: OS・コンパイラ・Apache・OpenSSL・Python・ImageMagick。
- `stage.log` / `restage.log` / `check-plist.log` / `stage-qa.log` / `package.log`: 最終Port結果。
- `package-info.log` / `artifact-sha256.log`: 検証パッケージとImageMagick 6有効モジュールの識別。パッケージのTHUMBNAILは無効。
- `native.log` / `migration.log` / `http.log` / `https.log` / `hardening.log` / `audit.log`: 既存試験とルーティング単体試験。
- `root-http.log` / `root-thumbnail-http.log` / `root-samples.log`: 今回追加の実HTTP試験。
- `sanitizer.log` / `routing-sanitizer.log`: ASan/UBSan。
- `static.log` / `static-analysis/`: 43翻訳単位の解析結果。未使用代入警告1件は残存。
- `compiled-match.log` / `source-hashes.json`: 転送した290ファイルのハッシュと、Port・ImageMagick有効ビルドの178入力ファイルを比較。テキスト比較時はCRLFをLFへ統一。再生成された`MessageJA.h`はSVN Idコメント1行だけを除いて一致を確認。
- `shutdown-check.log`: 検証Apacheの残存とコアファイルを確認。
- `baseline.log`: リビジョン5でルート配置のエラーを再現。
- `*-initial.log`: 途中の失敗記録。最終結果ではない。
- `thumbnail-build.log` / `thumbnail-link.log`: ImageMagick 6有効の直接ビルド。前者でコンパイル後に旧`-L`引数によるリンク失敗、修正後の後者でリンク成功。

再実行の例（BUILDはPort展開・ビルド済みソース、THUMB_BUILDはImageMagick有効の直接ビルド先、WORKは専用作業ディレクトリ）:

```sh
sh tests/run_native.sh
python3 tests/handler_test.py
python3 tests/locker_test.py
python3 tests/root_http_test.py --build-root "$BUILD" --workdir "$WORK"
python3 tests/root_http_test.py --build-root "$THUMB_BUILD" --workdir "$WORK" --thumbnail
python3 tests/root_sample_test.py --build-root "$BUILD" --workdir "$WORK"
```

HTTP試験にはFreeBSDのApache実行ファイル・モジュール、OpenSSL・htpasswd・生成済みテンプレートが必要です。既存の移行・監査試験の実行方法は隣接する履歴ログとtests内の引数を参照してください。旧モジュールへのバックアップ復元検査には対応する旧ビルドも必要です。

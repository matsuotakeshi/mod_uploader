# Portリビジョン4の検証記録

FreeBSD 15.1 amd64、Clang 19.1.7、Apache 2.4.69、OpenSSL 3.5.6。THUMBNAIL無効。本番サービスや本番データは変更していません。

- `stage.log`: クリーンビルドとstageに成功。既存のコンパイル警告も保持。
- `check-plist.log` / `stage-qa.log` / `package.log`: 全て終了コード0。
- `native.log`: 既存試験と追加20チェックに成功。時刻は注入、スレッド・プロセス・カーネルflockは実物。
- `locker.log`: 実クラスをコンパイルしAPR戻り値を注入、6チェック。実OS/APR障害の再現ではありません。
- `handler.log`: 実ハンドラ本体とhttpd代替の5チェック。
- `migration.log`: 38チェック。
- `http.log`: 44チェック、実Apacheと旧モジュールへのバックアップ復旧。
- `https.log`: 6チェック、検証用CAを明示してTLS証明書を検証。
- `hardening-http.log`: 41チェック、実リバースプロキシ・バックエンド、管理認証、IP/同時枠、並行要求、再起動。
- `source-hashes.log` / `compiled-match.log`: 転送ソースと検証対象の対応。主要な新規/修正実装3ファイルは実際のPortビルドツリーとバイト一致を確認。
- `package-info.log` / `package-sha256.log`: 生成パッケージの情報とSHA256。

ログの専用テストディレクトリは`<test-dir>`に置換しました。EUC-JPを含むビルド出力の非UTF-8部分は置換文字で収録しています。認証用fixture、秘密鍵、Cookie、移行バックアップ、本番データは収録していません。

詳細な確認範囲・未検証事項は[報告書](../../FREEBSD-ja.md)と[運用手順](../../SECURITY-MIGRATION-ja.md)を参照してください。

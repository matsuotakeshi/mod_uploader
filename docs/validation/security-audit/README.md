# Portリビジョン5の検証記録

FreeBSD 15.1-RELEASE amd64、Clang 19.1.7、Apache 2.4.69、OpenSSL 3.5.6。THUMBNAIL無効。本番サービスと本番データは変更していません。

| 記録 | 内容 |
| --- | --- |
| `environment.log` | 実測のOS・ツール・Portリビジョン・選択オプション |
| `baseline-reproduction.log` | 修正前リビジョン4で無効投稿による既存ファイル削除を再現 |
| `core-backtrace.log` | 修正前のApache停止時SIGSEGVのバックトレース。コア本体は非収録 |
| `stage.log` | 最終版のクリーンビルドとstage。既存のコンパイル警告も保持 |
| `check-plist.log`, `stage-qa.log`, `package.log` | すべて終了コード0 |
| `native-regression.log` | C++試験とAPR/httpd代替・失敗注入試験 |
| `migration.log` | 38チェック |
| `http-security.log` | 44チェック、実Apache、旧形式移行とバックアップ復元・旧版への復旧 |
| `https-security.log` | 6チェック、証明書を明示的に信頼する実TLS接続 |
| `hardening-http.log` | 41チェック、実プロキシ・認証・IP枠・同時枠・再起動 |
| `audit-http.log` | 20チェック、今回追加した不正入力・破損データ・容量・並行要求 |
| `sanitizer.log` | ASan+UBSan 2,115チェック。ヒープで共有領域の境界を代替、ロックのタイムアウト判定を注入。リーク検査無効 |
| `static-analysis.log`, `static-analysis/summary.json` | 実構成の43翻訳単位。未使用代入警告1、解析時コンパイルエラー0。各ソースの診断も収録 |
| `source-hashes.json`, `compiled-match.log` | 転送ソースのSHA256と、改変実装・手順等のPortビルドツリーとの対応 |
| `package-info.log`, `package-sha256.log` | 生成パッケージ情報とSHA256 |
| `shutdown-check.log` | 最終試験の停止結果と、以前のコアが更新されていないことの補助確認 |

`http-security-initial.log`と`audit-http-initial.log`は途中の失敗を保存したものです。前者は重複フォーム拒否の期待値、後者はApacheが起動時の設定検査前にTCP待受を始めることによる試験側の誤判定です。試験を修正して再実行しました。続いてログ収集中に停止時クラッシュを発見し、設定プールの寿命を製品コードで修正しました。最終HTTP群では通常停止の終了コード0、不正データでの起動はシグナル終了ではない正のエラー終了コードを要求します。

ログ内の専用テストディレクトリは`<test-dir>`へ置換しています。ビルドログ等の非UTF-8部分は置換文字で収録しました。認証用fixture、秘密鍵、Cookie、移行バックアップ、コア本体、本番データは収録していません。チェック件数は各試験内のassert等の数であり、網羅率ではありません。

調査範囲と残る制約は[監査報告](../../SECURITY-AUDIT-ja.md)と[移行・運用手順](../../SECURITY-MIGRATION-ja.md)を参照してください。

# mod_uploader 3.2.0 FreeBSD / Apache 2.4 改修・検証報告

更新日: 2026-10-24（日本時間）。このリポジトリは改変版です。

## 現在の確認状況

FreeBSD 15.1-RELEASE / amd64、Clang 19.1.7、Apache 2.4.69の環境で、Portからのモジュールビルド、stage、check-plist、stage-qa、packageを実行し、すべて終了コード0でした。THUMBNAILは無効です。利用者からは以前の版について実際に動作したとの報告があります。

今回の検証では、作成したパッケージのインストール、既存Apacheの再起動、ブラウザでの全機能試験は行っていません。ビルド・パッケージ作成の成功を、HTTP動作やインターネット公開時の安全性の保証とは扱いません。

| 項目 | 結果 | 証拠 |
|---|---|---|
| make stage | 成功 | [stageログ](validation/freebsd-stage-fixed.log) |
| make check-plist | 成功・不足/余分な項目なし | [check-plistログ](validation/freebsd-check-plist.log) |
| make stage-qa | 成功 | [stage-qaログ](validation/freebsd-stage-qa.log) |
| make package | 成功 | [packageログ](validation/freebsd-package.log) |
| pkg info -F / SHA-256 | 作成物のメタデータとハッシュを確認 | [package-infoログ](validation/freebsd-package-info.log) |
| FreeBSDでのC++回帰テスト | 80,012 + 7 + 7 + 16チェック成功 | [回帰テストログ](validation/freebsd-native-freebsd.log) |
| Apacheハンドラーの抽出テスト | 5チェック成功・httpd APIは模擬 | 同上 |

環境の依存パッケージはAPR `1.7.6.1.6.3`、GNU make `4.4.1`、libtool `2.6.2`、Perl `5.42.2`です。テスト用ホストのホームディレクトリ内に隔離した作業場所、distfiles、WRKDIRPREFIXを作成しました。システムのApache設定や稼働データを変更していません。公開ログでは作業場所を`<review-dir>`に置換しています。ログ中の一部の日本語メッセージは文字コード変換で置換文字になっていますが、実行結果・コンパイラ診断・終了コードは収録しています。

FreeBSDで作成したパッケージは `ap24-mod_uploader-3.2.0_2.pkg`、ABIは `FreeBSD:15:amd64`です。他のFreeBSDメジャー版・CPU向けとしては検証していません。

## 上流・ライセンス

- 改修版Fork: https://github.com/matsuotakeshi/mod_uploader
- 原作者: Tetsuya Kimata。上流: https://github.com/kimata/mod_uploader
- 基準コミット: `31632a29138b18b7adbf533416a0ec660f1b07ac`（ソース表記3.2.0）
- 原著作権表示とCOPYINGは保持し、MODIFICATIONSと変更箇所で改変版と明記しています。
- Portは`LICENSE=ZLIB`、`LICENSE_FILE=${WRKSRC}/COPYING`を使用し、COPYINGとMODIFICATIONSもインストールします。
- MAINTAINER: `takeshi@ysni.org`。WWWは改修版Forkです。

## 構造と依存関係

Apacheモジュールの入口は `src/mod_uploader.cpp`、機能のルーティングは `src/uploader_handler.cpp` です。ApacheResponse/RequestReader/ResponseWriterがApache・APRとの境界を担当します。RFC1867Parser/MultipartMessageParserが投稿データを解析し、UploadItem/UploadItemIO/UploadItemManagerが保存・管理を担当します。tmpl/css/img/jsに既存の画面資産があります。CGI・standalone経路も存在しますが、今回のHTTP受入試験対象ではありません。

主な依存はApache 2.4、APR、C++標準ライブラリ、iconv、ビルド用のGNU make・Perl・libtoolです。サムネイルはオプションでMagick++に依存し、gzipはzlibに依存します。

## 実装した主な変更

- C++11を明示しauto_ptrをunique_ptrへ置換。固定の`-lstdc++`を除去し、Clang/libc++に対応。
- ビルドフラグとライブラリのリンク順、/bin/bash固定、不要なPCH依存、md5sum依存、libtool判定を修正。
- Apache 2.4ではrequest単位のuseragent_ip/useragent_addrを参照。
- 受信バケットを呼び出し側のバッファ容量で分割し、読取エラー・メタデータ・EOSを処理。
- バッファ終端の1バイトを確保し、release時も境界検査、erase後の終端更新、確保失敗時の元バッファ保持を実施。
- multipartの完全な区切りを照合し、本文内の裸のboundaryとの誤認を抑止。サイズ超過を追加・書込み前に検査。
- 項目名とパスワードの前方一致を完全一致に変更。ヘッダーNUL、boundary、パラメータ終端、ファイル名を検査。
- リクエストプールで一時ファイルをcleanupし、古い無関係なファイルを掃除対象から除外。
- 通常のアップロードファイルはoctet-stream / attachment / nosniff / sandboxで配信。
- 画像例外のメッセージ寿命を修正。ハンドラーのNULL検査と最外層の例外捕捉を追加。
- Apache POSTでは、Originがある場合はBaseUrlと同一originであることを必須とし、不在時はRefererを検査。両方不在、不正Origin、cross-siteは403。

POSTのOriginとRefererは認証の代用ではありません。非ブラウザクライアントはこれらを偽装できます。curl・メール投稿等の既存スクリプトも、正しいOriginを付ける必要があります。scheme/host/portを正確に一致させます（既定ポートの省略と明示は同一視しません）。Originが不正な場合はRefererにフォールバックしません。リバースプロキシ配下ではBaseUrlと公開URL、信頼するプロキシの設定を一致させてください。

既存テンプレート、CSS、画像、JavaScriptのデザインは維持しています。通常ファイルのインライン表示を添付ダウンロードへ変更した点と、入力・POST検証の厳格化は意図した動作変更です。Flash機能が現代のブラウザで動くとは扱っていません。

## Portの検証で追加修正した問題

1. PortのMakefileがCRLFで、BSD makeが継続行を解釈できず停止していました。PortとテストをLFに統一し、.gitattributesに設定を追加しました。
2. GitHub distfile名にPORTVERSIONが含まれるのに、distinfoが省略していました。実際にPortsが要求する名称へ修正しました。アーカイブのSHA-256とサイズは実取得データで一致しました。
3. MAINTAINER、WWW、報告書内のパスと検証記録の参照を修正しました。

Portの場所は一貫して `ports/www/mod_uploader/` です。Portは固定した上流アーカイブと同梱パッチを使います。改修版Forkの移動するブランチを直接ビルド対象にはしていません。

## 再現手順

FreeBSDのPortsツリーと依存パッケージを用意し、隔離した作業場所で実行します。実際の検証は一般ユーザー権限で行いました。

```sh
cd ports/www/mod_uploader
TASKDIR=$(mktemp -d "$HOME/mod-uploader-check.XXXXXX")
make BATCH=yes WRKDIRPREFIX="$TASKDIR/work" DISTDIR="$TASKDIR/distfiles" stage
make BATCH=yes WRKDIRPREFIX="$TASKDIR/work" DISTDIR="$TASKDIR/distfiles" check-plist
make BATCH=yes WRKDIRPREFIX="$TASKDIR/work" DISTDIR="$TASKDIR/distfiles" stage-qa
make BATCH=yes WRKDIRPREFIX="$TASKDIR/work" DISTDIR="$TASKDIR/distfiles" package
```

作成されたパッケージはWRKDIR配下の`pkg/`に入る場合があります。`make -V WRKDIR -V PKGFILE`と実ファイルを確認してください。make makesumで既存のdistinfoを無条件に更新する必要はありません。

ソース回帰テスト:

```sh
sh tests/run_native.sh
python3 tests/handler_test.py
```

回帰テストでは、境界照合とorigin照合は実ヘルパー、バッファは実バッファ実装を使います。受信処理とハンドラーは実関数を使いますが、httpd/APRのAPIは模擬です。モジュールをビルドした事実とは別に、HTTPでの統合確認が必要です。

## 残課題とインターネット公開条件

**パスワードの平文保存は未解決です。インターネット公開可能との判定はしていません。**

現在の固定長パスワードフィールドにハッシュ値を単純に書き込むと、切り詰めや既存データ破損を招きます。Argon2id等の保存方式、バージョン付きメタデータ、バックアップ、移行・復旧、旧形式の扱い、認証試行制限を含む設計・実装・試験が必要です。今回、既存の保存形式を黙って変更してはいません。

- POSTの送信元検査は強化しましたが、トークン式のCSRF対策は未実装です。
- 外部公開する前にHTTPS、認証、接続・試行制限、admin/mailの制限を設定し、保存領域をDocumentRootやAliasで直接公開しないでください。設定例は引き続きRequire localです。
- パッケージのインストール／アンインストール、poudriere、非標準PREFIX・他のFreeBSD版・THUMBNAIL有効は未検証です。
- 既存Apacheへのロード、Origin/Referer検査を含むHTTP操作、アップロードと取得物のSHA-256一致、HEAD/Range/RSS、並行処理、graceful restart、ディスク満杯、旧データ移行は今回未検証です。
- コンパイルにはLockerデストラクターからのthrow、関数ポインターcast等の既存警告が残っています。ログに保持し、隠していません。
- 画像デコーダのcoder/delegate/resource policy、破損・巨大画像、CGI、standalone、gzip、全ルートの包括的セキュリティ監査は未完了です。

## 参照

- [改修版Fork](https://github.com/matsuotakeshi/mod_uploader)
- [Apache 2.4 API changes](https://httpd.apache.org/docs/2.4/developer/new_api_2_4.html)
- [FreeBSD Porter's Handbook](https://docs.freebsd.org/en/books/porters-handbook/)
- [OWASP CSRF Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html)
- [OWASP Password Storage](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)

# mod_uploader 3.2.0 FreeBSD / Apache 2.4 改修・検証報告

更新日: 2026-10-24（日本時間）。このリポジトリは改変版です。

## 現在の確認状況

最新はPortリビジョン5です。全体のセキュリティ調査で見つかった問題、修正内容、最新の検証結果・未検証事項は[セキュリティ監査報告](SECURITY-AUDIT-ja.md)を参照してください。以下のリビジョン2〜4の記録は履歴として保持しています。

FreeBSD 15.1-RELEASE / amd64、Clang 19.1.7、Apache 2.4.69の環境で、Portからのモジュールビルド、stage、check-plist、stage-qa、packageを実行し、すべて終了コード0でした。THUMBNAILは無効です。利用者からは以前の版について実際に動作したとの報告があります。

既存Apacheの再起動や本番パッケージのインストール、ブラウザでの全機能試験は行っていません。後述のセキュリティ更新では、別プロセスのApacheを127.0.0.1で起動してHTTP/HTTPSを検証しました。ビルド・パッケージ作成の成功を、HTTP動作やインターネット公開時の安全性の保証とは扱いません。

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

初回移植のログにあるリビジョン2と、後述するセキュリティ更新のリビジョン3は区別してください。

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

## パスワード移行・CSRF対策の実装と検証

現行メタデータの平文パスワードを廃止し、保存形式4.0.0に更新しました。PBKDF2-HMAC-SHA256（600,000回、16バイトランダムsalt）を使用します。旧形式2/3は新版の起動時に拒否し、停止中にバックアップを検証してから専用ツールで変換します。稼働中の新版との排他、途中中断時の起動防止マーカー、原本バックアップからの復旧を実装しています。

Apache POSTには、ブラウザCookieに結び付いた、有効期間2時間のHMAC-SHA256署名付きCSRFトークンが必要です。Origin/Referer検査も維持します。通常・管理フォームと、スクリプト用X-CSRF-Tokenに対応します。HTTPSでは__Host CookieとSecure/HttpOnly/SameSite=Strictを使用します。

**既存インストールへ上書きする前に、[移行・旧版復旧手順](SECURITY-MIGRATION-ja.md)を読んでください。** 本番データへ自動適用する更新ではありません。今回の検証も専用の試験データで行い、稼働Apacheや本番保存領域を変更していません。

### セキュリティ更新のFreeBSD検証

FreeBSD 15.1 amd64 / Clang 19.1.7 / Apache 2.4.69、THUMBNAIL無効で実行しました。保存形式4導入時のパッケージは `ap24-mod_uploader-3.2.0_3.pkg` です。上記の `_2` の記録は初回移植時の履歴として保持しています。

| 検査 | 結果 | 証拠 |
|---|---|---|
| 新形式と移行ツールのPortビルド・stage | 成功 | [stage](validation/security-format4/stage-final.log) |
| check-plist / stage-qa / package | すべて終了0 | [一覧](validation/security-format4/security-results.log) |
| パッケージ情報・SHA-256 | 確認 | [package-info](validation/security-format4/security-package-info.log) |
| ネイティブ回帰・暗号ヘルパー | 成功、暗号21チェックを含む | [native](validation/security-format4/security-native.log) |
| 旧形式2/3の移行、バックアップ、失敗、中断、復旧 | 38チェック成功 | [migration](validation/security-format4/migration-final.log) |
| パッケージが使うPython 3.11での同じ移行試験 | 38チェック成功 | [Python 3.11](validation/security-format4/migration-python311.log) |
| 実HTTP、パスワード認証、投稿・削除、CSRF、再起動、旧モジュールへの復旧 | 44チェック成功 | [HTTP](validation/security-format4/http-security-final.log) |
| 実HTTPS、試験証明書の検証、__Host Cookie、トークン付きPOST | 6チェック成功 | [HTTPS](validation/security-format4/https-security-final.log) |
| 検証ソースの一致 | 15ファイルと製品パッチをSHA-256で照合 | [ソースハッシュ](validation/security-format4/security-source-hashes.log) |

移行試験では独立したPython PBKDF2計算で結果を照合し、空パスワード、同じデータの再実行、バックアップ先の上書き拒否、破損・リンクの拒否、最初の置換直後に注入した中断とバックアップ復旧を確認しました。

実HTTPでは、旧形式を新版が拒否すること、新版稼働中の移行拒否、12クライアントの同時セッション作成、トークン不在・改ざん・期限切れ・将来時刻・別セッション・重複Cookie/トークン、不正Origin、不正ヘッダートークンを確認しました。旧パスワードの完全一致、新規投稿がハッシュ保存されること、通常/管理の削除、取得物の内容一致、複数タブ、再起動後のトークン継続も確認しました。バックアップを別ディレクトリへ復元し、旧モジュールで取得できることを確認しています。

検証中に見つかった、削除パスワード項目が欠落した要求でNULLを参照する既存処理も修正し、実HTTPで拒否応答を確認しました。

### 残る確認範囲

- 実際の本番データの移行は行っていません。旧版には新版の排他ロックがないため、旧版を完全停止する作業は利用者が必要です。
- バックアップには旧平文パスワードが残ります。0700の外側ディレクトリで保護し、公開しないでください。
- パッケージの本番インストール/アンインストール、poudriere、他ABI、THUMBNAIL有効、巨大データセット、電源断の実機注入、全ブラウザ、全面的なセキュリティ監査は未検証です。
- HTTPS、管理者認証・接続制限、認証試行・リクエスト量の制限、保存領域の非公開設定は引き続き必要です。トークンは認証の代用ではありません。
- リビジョン3のログには既存のLockerデストラクターの警告があります。リビジョン4で非送出の後処理へ修正しました。その他の既存警告はビルドログに記録しています。
- CGI/standalone/Apache 1.xのPOSTは保護方式に未対応のため拒否します。Flashはサポート対象外です。

## 追加セキュリティ修正（Portリビジョン4）

保存形式は4のままです。既にリビジョン3で移行済みならパスワードの再変換は不要です。更新前にバックアップし、Apacheを完全停止して新モジュール・設定を適用してください。管理画面の利用には専用Apache認証の追加設定が必要です。

管理画面はApacheが認証済みの利用者のみ許可します。`Require local`だけの場合は、実際のlocalhost接続でも管理操作を403で拒否します。Port設定例は管理画面を既定で閉鎖します。専用の認証ファイルとHTTPS等の管理経路が必要です。管理画面・管理取得・管理削除・設定情報表示の全てを対象にしました。

パスワード照合と投稿時のハッシュ作成は、同一IPあたり60秒の固定窓で10リクエスト、同じ保存領域の全ワーカーで同時2リクエストまでです。成功も数え、超過時はHTTP 429とRetry-Afterを返します。GET/空入力で高コストの照合を行いません。状態は固定サイズのファイルに保存し、プロセス間・スレッド間で共有します。異なるIPのハッシュ衝突は枠を共有する保守的な方式です。転送ヘッダーは独自には信用しません。詳細とプロキシ構成上の注意は[運用手順](SECURITY-MIGRATION-ja.md)を参照してください。

`Locker`のデストラクタは非送出とし、APR解除失敗時は状態コードを標準エラーへ記録します。例外処理中の二重例外を避け、失敗時はロック中のフラグを保持します。実際のOS/APR障害を回復する機能ではありません。

FreeBSD 15.1 amd64 / Clang 19.1.7 / Apache 2.4.69 / OpenSSL 3.5.6、THUMBNAIL無効で追加検証しました。本番Apache・本番データは変更していません。パッケージは`ap24-mod_uploader-3.2.0_4.pkg`です。

| 検証 | 結果 | 記録 |
| --- | --- | --- |
| Portのクリーンビルド・stage | 成功 | [ビルド](validation/security-hardening/stage.log) |
| check-plist / stage-qa / package | 全て成功 | [一覧](validation/security-hardening/check-plist.log)、[QA](validation/security-hardening/stage-qa.log)、[package](validation/security-hardening/package.log) |
| 既存のネイティブ試験＋新規スロット/回数試験 | 成功、追加20チェック | [ネイティブ](validation/security-hardening/native.log) |
| Lockerの実クラスを用いたAPRエラー注入 | 6チェック成功 | [Locker](validation/security-hardening/locker.log) |
| ハンドラ例外処理（httpd代替） | 5チェック成功 | [ハンドラ](validation/security-hardening/handler.log) |
| 旧データ移行・バックアップ・中断復旧 | 38チェック成功 | [移行](validation/security-hardening/migration.log) |
| 実Apacheの既存HTTP試験・旧モジュールへの復旧 | 44チェック成功 | [HTTP](validation/security-hardening/http.log) |
| 実TLSの既存HTTPS試験 | 6チェック成功 | [HTTPS](validation/security-hardening/https.log) |
| 実プロキシ・管理者認証・試行回数・同時枠・再起動 | 41チェック成功 | [追加HTTP](validation/security-hardening/hardening-http.log) |

追加HTTPでは、管理経路へのGET/削除POST、設定情報、管理ダウンロード、エンコードされたパス、偽装利用者ヘッダーを未認証で拒否することを確認しました。専用Basic認証の失敗・成功と、認証後も削除にCSRFが必要なことを確認しました。公開プロキシ側での独立した遮断も確認しました。

試行制限は、別Cookie・別CSRFトークン・偽装転送IPでも同じ接続元枠を消費すること、正しいパスワード・削除・パスワード付き投稿にも上限が働くこと、429時に投稿一時ファイルが残らないこと、再起動後の上限維持を確認しました。並行HTTP要求と、実ファイルロックで全同時枠を占有した場合の拒否・解放後の取得成功を確認しました。ネイティブ試験では固定時刻注入による窓境界・時計逆行と、別プロセス・スレッドの共有およびSIGKILL後の枠解放を確認しています。

未検証: 本番導入・既存本番プロキシの設定、管理者認証システムの全組合せ、実際のAPR解除障害、実時計変更・OS電源断、他ABI、THUMBNAIL有効、巨大データ、poudriere、全ブラウザ。管理者Basic認証そのものの試行制限や分散アクセス・通信量制限は公開側で別途設定してください。固定窓境界では短時間に最大20回となり得ます。IP枠を共有するプロキシ/NATやハッシュ衝突では正当な利用者も制限され得ます。OS/APR解除障害の試験は戻り値の注入であり、実障害の発生・回復を確認したものではありません。

## 参照

- [改修版Fork](https://github.com/matsuotakeshi/mod_uploader)
- [Apache 2.4 API changes](https://httpd.apache.org/docs/2.4/developer/new_api_2_4.html)
- [FreeBSD Porter's Handbook](https://docs.freebsd.org/en/books/porters-handbook/)
- [OWASP CSRF Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html)
- [OWASP Password Storage](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)

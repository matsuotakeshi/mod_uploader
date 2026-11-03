# mod_uploader 3.2.0_7 運用改修・検証結果

検証日: 2026-11-03。基準は改修版 `6c447be275e8c4d03656a03fdfc7b8ebfa7e8b5c`（Port revision 6）。原作者のコードとzlibライセンス表示を維持した改変版です。

依頼された5分野の実装と、利用できるFreeBSD環境での検証を実施しました。本番の保存領域非公開、認証・保護、Certbotドライランは管理者の確認済み事項として扱っています。本作業では本番のモジュール、Apache設定、保存データ、システムパッケージを交換・再起動・初期化していません。

## 変更と確認結果

| 分野 | 見つかった問題・変更 | 確認した範囲 |
| --- | --- | --- |
| バックアップ・復旧 | 停止確認、稼働中ロック拒否、SHA-256照合、新規領域限定の復元、救済バックアップを伴うジャーナル復旧を追加 | 内容改変・リンク・領域外パスの拒否、別領域への復元後にApacheで取得 |
| 書き込み障害 | 容量調整で旧投稿を消した後、新規保存が失敗すると旧投稿を失う余地があった | 新規ファイルを先にステージし、旧投稿を復元可能な名前へ移動、fsyncと確定記録を追加。例外、プロセス中断、書き込み・rename・fsync失敗を試験 |
| 画像処理 | デコーダ・delegate・処理時間や資源の制限が不足 | JPEG/PNG/GIF/WebPだけを対象とし、画素数・メモリ・CPU・出力・時間を制限。SVG/PDF/MVG、破損・過大PNGで元ファイル保持とサムネイル非生成を確認 |
| 負荷・監視 | エラー本文にHTTP 200を返す箇所、ロックの長い待機、保存容量の監視手段不足 | 400/403/404/413/429/503等を返すよう修正。sleepを伴う15秒のロック待機上限、読取専用容量検査を追加。既存のIP別・同時照合制限を再検証 |
| Port・依存関係 | 直接ビルドのiconvリンクがImageMagickの間接依存に隠されていた。検証機の依存パッケージにもVuXML警告 | 選択されたiconvヘッダを使ってリンク可否を判定。Port標準のbase iconvと直接ビルドのGNU libiconvを確認。THUMBNAIL依存をImageMagick 7の修正版以上へ指定 |
| 残存コード | ファイルサイズの符号・範囲変換、設定整数の不正値、メタデータ書き込み確定処理 | 明示的な範囲検査、数値設定の拒否、メタデータのwrite-full/fsync/rename、警告の一部整理を実施 |

主な変更ファイル:

- `include/StorageTransaction.h`、`src/UploadItemManager.cpp`、`src/UploadItemWriter.cpp`、`src/UploadItemIO.cpp`: 保存・削除・容量調整のトランザクションと復旧記録。
- `util/storage_backup.py`、`storage_recover.py`、`storage_health.py`、`dependency_audit.py`: 管理者用の運用ツール。
- `src/ImageFile.cpp`、`include/ReadWriteLocker.h`: 画像の制限とロック待機。
- `include/HttpErrorStatus.h`、`include/ConfigNumber.h`、`src/uploader_handler.cpp`、`src/mod_uploader.cpp`: HTTPエラーと設定値検査。
- `include/File.h`等、`configure.ac`、`configure`、`src/GNUmakefile.in`: 整数範囲、iconv検出、Clang向け調整。
- `ports/www/mod_uploader/`、`tests/`、`docs/OPERATIONS-ja.md`: rev7 Port、設定例、回帰試験、運用・復旧手順。

## 実機環境

FreeBSD 15.1-RELEASE amd64、Clang 19.1.7、Apache 2.4.69、APR/APR-utilパッケージ1.7.6.1.6.3。一般ユーザーの新規作業ディレクトリ、loopback上の別ポート、専用データで実行しました。

- ImageMagick 6: システムの6.9.13.50を互換性試験に利用。既知警告があるため、このバージョンの公開運用を認定したものではありません。
- ImageMagick 7: 7.1.2-35、ソースcommit `5d1bcc55f2c83bc2ff802118b73699756610f3ad4` を専用prefixにビルド。Q16、HDRIなし、JPEG/PNG/WebPを利用可能とし、多くの任意delegateを無効化。`LD_LIBRARY_PATH` は検証プロセスだけに設定しました。
- Port: THUMBNAIL無効の標準設定、システムの依存パッケージを利用。パッケージはシステムへ `pkg add` せず、新規領域へ展開して実際のモジュールと収録ツールを起動しました。
- ソースZIP: FreeBSDで新規展開し、実行権限を含めて `./configure`、`gmake -j2 apache-module password-tool`、ImageMagick 7を使う実HTTP試験を実施しました。

## 自動試験

件数は各スクリプトのassertion/check数です。同じ試験の異なるビルドでの実行を含む延べ件数であり、脆弱性の網羅数ではありません。最終実行は下記すべて成功し、失敗0でした。

| 試験 | 成功件数 | 内容・ログ |
| --- | ---: | --- |
| native | 80,191 | 安全性、バッファ、reader、Origin、暗号・トークン、試行制限、routing、HTTP status、設定整数。[ログ](validation/operations/native-tests.log) |
| storage | 655 | 実C++保存処理への例外・中断・syscall失敗注入、バックアップ・復旧・パス拒否。[ログ](validation/operations/storage-test.log) |
| HTTP security | 42 | 実Apache、パスワード、CSRF、再起動。[ログ](validation/operations/security_http-final.log) |
| HTTPS security | 6 | ローカル検証用証明書の検証、cookie、保護POST。[ログ](validation/operations/security_https-final.log) |
| hardening HTTP | 41 | loopbackプロキシ、管理認証、共有IP試行制限・同時照合上限。[ログ](validation/operations/hardening_http-final.log) |
| audit HTTP | 20 | 不正投稿、破損メタデータ、欠落payload、容量、16投稿/8並列ワーカー等。[ログ](validation/operations/audit_http-final.log) |
| password migration | 38 | 旧形式2/3、バックアップ、中断、破損・リンク拒否。[ログ](validation/operations/migration-final.log) |
| handler / Locker | 5 / 6 | mock httpd、実デストラクタへのAPR失敗注入。実APRのunlock障害再現ではありません。[handler](validation/operations/handler-test.log)、[Locker](validation/operations/locker-test.log) |
| ASan + UBSan | 2,118 | 実APR/parser/listと追加の整数境界。全Apacheプロセスのsanitizer実行ではありません。Leak検出は無効。[ログ](validation/operations/sanitizer.log) |
| root/subpath + HTTP/HTTPS | 946 × 3、841 × 1 | IM6、IM7、ZIPのサムネイル有効版、Portの無効版。各7構成。静的ファイルはstatusだけでなくMIME・本文も検査。[IM6](validation/operations/root-http.log)、[IM7](validation/operations/root-im7.log)、[ZIP](validation/operations/root-zip.log)、[Port](validation/operations/root-port.log) |
| 配布Apache設定例 | 20 × 2 | ルート・サブパスの日本語設定例をIM7版とPort版で試験。[IM7](validation/operations/root_sample-final.log)、[Port](validation/operations/samples-port.log) |
| operations HTTP | 73 × 3、54 × 2 | IM6、IM7、ZIP、Portビルド、展開したpkg。実権限エラー時の旧投稿保持、画像、日本語名、復元後取得、未完了記録による起動拒否、復旧。[IM6](validation/operations/operations-im6-final.log)、[IM7](validation/operations/operations-im7.log)、[ZIP](validation/operations/operations-zip.log)、[Port](validation/operations/operations-port.log)、[pkg](validation/operations/package-test.log) |
| ZIP構成 | 78 | Windows/PythonでCRC、単一ルート、実行モード、68のUnixビルド入力のLFを確認。[ログ](validation/operations/source-archive.log) |

FreeBSD上の試験は延べ87,168件、ZIP構成検査を含め87,246件です。別途Clang静的解析は43翻訳単位を実行し、解析diagnostic 0・コンパイルエラー0でした。[解析結果](validation/operations/static-im7.log)

静的解析diagnostic 0は、通常ビルドの警告0を意味しません。通常のClangビルドには既存の符号変換等の警告が残ります。[ZIPビルドログ](validation/operations/zip-build.log)

追加試験中に、画像リスト上限1では正常PNGも拒否されることが分かり、内部一時画像を考慮して8へ修正しました。また、テストの容量指定を既存のKiB単位へ訂正し、日本語名の確認先を元の名前が表示される一覧へ訂正しています。これらの失敗実行を成功件数に含めていません。

## Portの検証

`BATCH=yes DEVELOPER=yes MAKE_JOBS_NUMBER=2`、専用WRKDIRPREFIX/DISTDIRで `stage check-plist stage-qa package` が完了しました。最終ログでplist欠落・余分なファイル、未宣言共有ライブラリ依存の指摘がないことを確認しました。`GNUmakefile` のSHELLが既に修正済みでREINPLACE_CMDが変更しなかった、という警告は1件残ります。[最終Portログ](validation/operations/port-release.log)

途中のビルドでは `stage-qa` の終了値が0でもlibiconvの依存エラーが出ました。終了値だけで合格にせず、configureを実際のヘッダとリンクに基づく検査へ直した後、新しいWRKDIRPREFIXで再ビルドしました。

最終pkgの依存はapache24、apr、python311です。THUMBNAIL無効版にImageMagick依存はありません。収録されたモジュール、テンプレート、password_tool、Python運用ツールを新規領域へ展開して54件の実HTTP試験を実施しました。pkgのSHA-256は[記録](validation/operations/package-sha256.txt)を参照してください。

改修したビルド・運用入力27ファイルについて、ローカルの完成ソース、IM6/IM7の検証ソース、ZIP展開ソース、Portがパッチ適用したソースを照合しました。改行とPortのPython shebang変換を除き差分はありません。[照合結果](validation/operations/input-comparison.log)

THUMBNAIL有効の通常Portパッケージとpoudriereでのクリーンjail検証は未実施です。検証ホストにpoudriere・権限昇格手段がなく、IM7は専用prefixへの直接ビルドで確認しました。これは依存パッケージを含む通常のPortインストール・削除の検証を代替しません。手順は [PORT-MATRIX.md](../tests/PORT-MATRIX.md) に記載しました。

## 依存ライブラリで残った警告

専用ディレクトリへ取得したVuXMLで、Apache/APR/ImageMagick/Python/libiconvと登録された依存先163パッケージを確認し、6パッケージに警告が出ました。監査ツールの終了値1は警告を示す正常な検出結果であり、「既知脆弱性なし」ではありません。[集計](validation/operations/dependency-audit.log)、[詳細](validation/operations/dependency-report.json)

| 検出パッケージ | 結果 |
| --- | --- |
| ImageMagick6-6.9.13.50_1,1 | 画像処理の複数脆弱性。[検出ログ](validation/operations/ImageMagick6-6.9.13.50_1,1.log) |
| brotli-1.2.0,1 | 範囲外書き込み。[検出ログ](validation/operations/brotli-1.2.0,1.log) |
| curl-8.22.0 | 複数の既知問題。[検出ログ](validation/operations/curl-8.22.0.log) |
| expat-2.8.1 | 複数の既知問題。[検出ログ](validation/operations/expat-2.8.1.log) |
| python311-3.11.15_2 / python312-3.12.15 | 標準ライブラリ等の警告。[3.11](validation/operations/python311-3.11.15_2.log)、[3.12](validation/operations/python312-3.12.15.log) |

検出はインストール済み版と公開情報の照合であり、各CVEがmod_uploaderから到達可能かをすべて実証した結果ではありません。今回の画像処理制限で依存ライブラリ自体の脆弱性が直ったとは扱いません。更新は別の管理作業として必要です。

PortのTHUMBNAIL依存は `ImageMagick7-nox11>=7.1.2.34` に変更しました。[VuXML](https://vuxml.freebsd.org/freebsd/fc4d0a5b-d0c6-11f1-bae2-3497f65b111b.html) の当日時点の修正版条件に基づきます。独立ビルドした7.1.2-35はpkg登録外のため、pkg auditがその構成全体を検査したとはしていません。

base OpenSSLは3.5.6、`freebsd-version -ku` はともに15.1-RELEASEでした。pkg auditの対象外です。[FreeBSD-SA-26:68.openssl](https://www.freebsd.org/security/advisories/FreeBSD-SA-26:68.openssl.asc) は15.1-RELEASE-p4での修正を案内しています。検証機でその修正が適用済みとは確認できていません。該当アドバイザリはDTLSの問題で、通常のApache HTTPSへの影響を実証したものではありません。独自バックポートの有無を含め、OSの更新状況は別途確認してください。

## 互換性・未検証事項

- ルート `/` とサブパス、既存画面・静的URL、認証・CSRF、形式4のパスワードを維持します。旧形式2/3には既存のオフライン移行が必要です。
- サイズ設定は従来どおりKiBです。Port例を合計1GiB・1ファイル10MiBの値へ訂正しました。設定の負数・0・桁あふれ・数字以外は拒否します。本番の既存値は変更していません。
- 画像生成はJPEG/PNG/GIF/WebPに限定され、大画像・アニメーションは制限で生成されない場合があります。元ファイルのアップロード・取得は維持します。
- エラーHTTP statusの変更により、自動クライアントは4xx/5xxの本文も扱う必要があります。
- 実際のディスク満杯、電源断、ストレージ故障、別ファイルシステム、ZFS/ACL、root所有者復元、UID/GIDが異なる別ホストへの復旧、長時間負荷、全画像コーデック・policy組合せ、別CPU/FreeBSD版は未検証です。
- ENOSPC/EIOはsyscall失敗注入、アクセス権エラーは実ファイル権限、プロセス中断は子プロセス終了で確認しました。ハードウェアの永続化保証まで試験したものではありません。
- 検証の一部では短時間に並列投稿するため `UPLOADER_DEBUG` を指定し投稿間隔を回避しています。通常の試行制限は別試験で確認しています。負荷試験から本番の最大同時接続数や持続性能は算出していません。
- バックアップ・監視ツールのcron/通知登録、保管世代や復旧目標の決定、本番データを使う復旧訓練は未実施です。ツールは本番停止や世代削除を自動化しません。
- 本番への適用と適用後の実利用確認は管理者の判断で別途行います。今回の検証から「脆弱性が一切ない」とは結論しません。

## 適用とロールバック

1. [運用手順](OPERATIONS-ja.md)に従い、依存更新と設定値・サムネイル有無を検討し、別領域で新モジュールをビルドします。
2. 本番Apacheを完全停止し、データ・ファイル・サムネイル・一時領域を検証付きでバックアップします。旧モジュール、設定、独自テンプレートも保存します。
3. 未完了記録がないこと、所有者・権限、`apachectl configtest` を確認し、管理者の操作で交換・起動します。ルート/サブパス、静的ファイル、投稿、取得、管理認証を確認します。
4. 問題があれば完全停止し、旧モジュール・設定・対応するデータバックアップを戻します。未完了ジャーナルを手動削除して旧版を起動せず、先に救済バックアップを伴う復旧を実施してください。

本報告書追加後の最終ZIPは、検証済みZIPとビルド入力を照合したうえでログ・報告書を追加したものです。配布ZIP内の `configure` は実行可能・LF形式です。

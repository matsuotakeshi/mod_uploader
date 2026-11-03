# 依存パッケージ更新とPort追加検証

実施日: 2026-11-03。基準ソースは `736eb03b32a21c264fa7a1558210b2eb2f13a6dd`（3.2.0_7）。Portの依存指定2点を修正して3.2.0_8としました。前回の [運用改修検証](OPERATIONS-VALIDATION-ja.md) で残った依存更新、OS側OpenSSL、poudriere、THUMBNAIL有効Portを対象とします。

## パッケージ更新

ユーザーが指定したFreeBSD検証ホストで、管理者権限による更新を実施しました。変更前に旧パッケージ、整合性確認済みのパッケージDBコピー、Apacheを含む `/usr/local/etc` 設定を管理者専用ディレクトリへ退避しました。旧パッケージ7個のアーカイブ読取とSHA-256記録も実施しました。

| パッケージ | 更新前 | 更新後 | 当日のVuXML再照合 |
| --- | --- | --- | --- |
| ImageMagick6 | 6.9.13.50_1,1 | 6.9.13.59,1 | 警告なし |
| brotli | 1.2.0,1 | 1.2.1,1 | 警告なし |
| curl | 8.22.0 | 8.23.0 | 警告なし |
| expat | 2.8.1 | 2.9.0 | 警告なし |
| python311 | 3.11.15_2 | 3.11.17 | POP3/IMAPの2警告が残る |
| python312 | 3.12.15 | 3.12.15（更新候補なし） | POP3/IMAPの2警告が残る |
| libheif（必要な依存更新） | 1.22.2_3 | 1.23.6 | 警告なし |

ホストのquarterlyリポジトリを更新して対象を指定した `pkg upgrade` を実行しました。削除はなく、上記5対象と必要なlibheifが更新されました。Python 3.12はquarterlyとlatestの両方で3.12.15が最新候補でした。latestの確認は別カタログで行い、システムのリポジトリ設定は切り替えていません。

関連163パッケージの再監査では、警告対象が6から2パッケージに減りました。これは「すべての警告が解消した」という結果ではありません。残った [CVE-2025-15367 / poplib](https://vuxml.freebsd.org/freebsd/6d3488ae-2e0f-11f1-88c7-00a098b42aeb.html) と [CVE-2025-15366 / imaplib](https://vuxml.freebsd.org/freebsd/0be929a5-2e0f-11f1-88c7-00a098b42aeb.html) は、利用中のPython系列が対象です。poplibについては上流が互換性への影響から旧系列への修正取り込みを保留しています。[Python上流の説明](https://github.com/python/cpython/pull/143924)

mod_uploaderの運用ツールはpoplib・imaplibを使用していません。ただし、このホストの他のアプリケーションがこれらを利用するかまでは確認していません。警告を消すためにPython系列を無断で置き換えたり、標準ライブラリを直接書き換えたりはしていません。

更新後の共有ライブラリ整合性検査は成功しました。既存Apacheの `configtest` はSyntax OKで、ServerName未設定の警告が残ります。既存モジュールのSHA-256は変更前と一致します。

## OS側OpenSSL

確認開始時のカーネル・稼働カーネル・ユーザーランドは15.1-RELEASE、OpenSSL表示は3.5.6でした。別作業領域で `freebsd-update fetch` を実行し、署名付き更新情報から15.1-RELEASE-p6への更新対象を確認しました。ホストのlibssl/libcryptoは更新対象に含まれ、修正済みp6 jailの同名ファイルともSHA-256が異なっていました。

[FreeBSD-SA-26:68.openssl](https://www.freebsd.org/security/advisories/FreeBSD-SA-26:68.openssl.asc) は15.1-RELEASE-p4で修正されています。問題はDTLSの再送処理であり、通常のApache HTTPS経由で悪用できることを実証したものではありません。pkg監査はbase OpenSSLを対象にしないため、パッケージの監査結果と分けています。

ホストでは更新の取得・比較までを実施し、`freebsd-update install` と再起動は実施していません。OS全体の更新対象にカーネルも含まれるため、適用・停止範囲は管理者の判断が必要です。したがって、OS側OpenSSLは修正適用済みとは報告できません。

現物のハッシュは署名検証された更新メタデータの旧ファイルと一致し、新ファイルとは異なります。[署名付きindexの該当部分](validation/dependency-port/openssl-signed-index.json)、[ホストと更新済みjailの比較](validation/dependency-port/openssl-patch-comparison.json)、[作業終了時のOS・Apache状態](validation/dependency-port/final-host-state.txt)。`fetch`中の「Applying patches」は取得用領域での準備であり、ホストへの適用結果ではありません。

## poudriereの検証環境

poudriere 3.4.8とrelease manifestを導入し、専用設定・専用保存先でFreeBSD 15.1-RELEASE-p6 amd64ユーザーランドのjailを作成しました。jailはホストの未更新カーネルを共有します。UFS環境のためNO_ZFS、メモリ約1GBのためtmpfs無効、各setの依存ビルド1並列としています。

Portsは2026Q4の独立checkout、commit `33445545dd3a920c6340bfe4efa7035c5129afdf`。ホストの `/usr/ports` を置き換えていません。THUMBNAIL有効/無効を別のpoudriere setで検証しました。依存パッケージは `-b quarterly` により公式バイナリを利用できる場合に取得し、対象Port自体はjail内でソースからビルドしました。全依存をソースから作り直した検証ではありません。

初回は両構成とも `pre-patch` で `/usr/local/bin/perl: not found` により停止しました。`USE_PERL5=build` だけでは、クリーンjailのパッチ段階にPerlがまだ入りません。`USE_PERL5=patch build` に訂正し、Port revisionを8へ上げました。モジュール本体・テンプレート・保存形式はrevision 7のままです。初回の `testport -I` は終了値0でも失敗ログを含んだため、終了値だけで合格とは判定していません。

THUMBNAIL有効版では次に `Magick++.h` を見つけられず停止しました。公式ImageMagick 7の `Magick++-config` が検索先を `lib/pkgconfig` に固定する一方、FreeBSDの `.pc` ファイルは `libdata/pkgconfig` に置かれていました。PortでTHUMBNAIL時のpkgconf依存と `PKG_CONFIG_PATH` を明示し、ヘッダ・リンク指定を取得できるように修正しました。システムのImageMagickスクリプトは書き換えていません。

最終Portで両構成とも、ビルド・stage-qa・check-plist・package・install・deinstallとファイルシステムの差分検査が成功しました。`-I`でテスト用に再インストールされたパッケージでHTTP試験を行い、終了後の`pkg check -s`も成功しました。[通常版ログ](validation/dependency-port/poudriere-plain.log)、[THUMBNAIL版ログ](validation/dependency-port/poudriere-thumb.log)、[パッケージSHA-256・依存・オプション](validation/dependency-port/release-packages.json)

THUMBNAIL版は公式 `ImageMagick7-nox11-7.1.2.34`（Q16 HDRI）を使用し、`ldd`で実際のモジュールがMagick++/Wand/Coreの7系列へリンクしていることを確認しました。通常版にImageMagick依存はありません。両方ともPythonは3.12.15です。jail内の関連依存監査は通常版23パッケージ、THUMBNAIL版162パッケージで、警告はどちらもPython 3.12の上記2件でした。

Clangのテンプレート静的メンバー参照、Apache/APRマクロ、初期化子等に関する既存の警告は残ります。ビルド成功を「警告ゼロ」や「脆弱性なし」とは扱いません。

## 更新後の実HTTP試験

ホストの更新済みImageMagick 6を使い、別ポート・新規データのApacheで、ルート/サブパス・HTTP/HTTPSの946件、画像・保存・復旧の73件を実行し、成功しました。後者はPython 3.11でも別途73件成功しました。これらは既存本番データでの試験ではありません。

| 最終実行 | 成功件数 | 失敗 | 証跡 |
| --- | ---: | ---: | --- |
| 更新済みホスト・ルート/サブパス HTTP/HTTPS | 946 | 0 | [ログ](validation/dependency-port/root-updated-host.log) |
| 更新済みホスト・画像/保存/復旧 | 73 | 0 | [ログ](validation/dependency-port/operations-updated-host.log) |
| 更新済みホスト・Python 3.11で画像/保存/復旧 | 73 | 0 | [ログ](validation/dependency-port/operations-python311.log) |
| 通常版パッケージ・HTTP/HTTPS | 841 | 0 | [ログ](validation/dependency-port/jail-plain/root_http.log) |
| 通常版パッケージ・保存/復旧 | 54 | 0 | [ログ](validation/dependency-port/jail-plain/operations_http.log) |
| 通常版パッケージ・収録設定例2種類 | 20 | 0 | [ログ](validation/dependency-port/jail-plain/root_sample.log) |
| THUMBNAIL版パッケージ・HTTP/HTTPS | 946 | 0 | [ログ](validation/dependency-port/jail-thumb/root_http.log) |
| THUMBNAIL版パッケージ・画像/保存/復旧 | 73 | 0 | [ログ](validation/dependency-port/jail-thumb/operations_http.log) |
| THUMBNAIL版パッケージ・収録設定例2種類 | 20 | 0 | [ログ](validation/dependency-port/jail-thumb/root_sample.log) |
| **合計** | **3,046** | **0** | 同じ試験の異なる構成での実行を含むassertion数 |

パッケージの実行試験はjail内の非特権ユーザーnobodyで行い、インストールされたモジュール・テンプレート・password_tool・Python運用ツール・設定例を使用しました。設定例では保存先・BaseUrl等をテスト領域へ置き換えています。JPEG/PNG/GIF/WebPの生成、SVG/PDF/MVG・破損/過大画像の拒否、元ファイル保持、実アクセス権エラー時の既存投稿保持、バックアップ復元後のApache配信を確認しました。画像・CSS・JSはパッケージ内の実ファイルです。

既存root HTTP試験のSWFルーティング確認にはソースのSWFを別途fixtureとして用意しました。PortはSWFを収録せず、Flashのブラウザ実行も試験していません。最初のPerl依存不足2実行、pkg-config検索失敗1実行は上表の最終成功件数に含めず、[失敗ログ](validation/dependency-port/)も残しました。

Python 3.11/3.12の運用ツールで使う標準モジュールのimportと、ハッシュ・圧縮・JSON処理も確認しました。初期の補助チェックでPython 3.11のSQLite拡張が見つからなかったため旧パッケージを確認し、更新前から本体パッケージに含まれない任意拡張であることを確認しました。追加インストールや、SQLiteが利用可能という報告はしていません。

## 検証範囲と証跡

今回追加で確認したのはFreeBSD 15.1 amd64・2026Q4・標準PREFIX・UFS・公式バイナリ依存を利用するpoudriereの2構成です。別FreeBSD版、別CPU、Ports main、全依存のソースビルド、ZFS、長時間負荷、本番データでの復旧訓練は未検証です。前回のnative/storage失敗注入試験は今回再実行せず、ソース変更がないことを確認し、実際のパッケージのビルドとHTTP試験を追加しました。

提出Portの8ファイルは、実機でビルドした入力とSHA-256で照合しました。[入力記録](validation/dependency-port/input-sha256.json)。報告書・ログ以外に実行コードは変えていません。初回失敗を含むログは [validation/dependency-port](validation/dependency-port/) に収録し、作業パス・ホスト名・端末制御文字を整理しています。秘密情報を含むバックアップは収録していません。

実行試験後、今回のテストjailを停止しました。再利用用のベースjail、Ports checkout、依存キャッシュ、生成パッケージ、ログは専用領域に保管しています。

## 復旧用保管物

旧パッケージ、パッケージDB、設定コピーは検証ホストの管理者専用領域に保持しています。認証情報・秘密鍵を含み得る設定コピーをGitHubや配布ZIPへ収録しません。

既存Apacheは再起動しておらず、稼働済みプロセスが旧共有ライブラリを保持する可能性があります。更新済みライブラリでの試験は今回新しく起動した隔離Apacheの結果です。既存サービスへの反映には、保守時間帯に関連プロセスを再起動し、実利用を確認する作業が残ります。新しいmod_uploaderパッケージも検証jailだけに導入し、本番モジュールは交換していません。

パッケージのロールバックは依存関係を確認したうえで旧アーカイブを使い、関連プロセスを再起動して確認します。Python 3.12は変更していません。DBファイルだけを戻すと実ファイルと不整合になるため、その方法では戻しません。公開中のアップロードデータを削除・初期化する手順はありません。

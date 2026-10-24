# mod_uploader 3.2.0 FreeBSD / Apache 2.4 移植報告

作業日: 2026-10-24（日本時間）

**状態: 利用者からFreeBSD／Apache環境で動作したとの報告あり。OS・Clang・Apacheの版および機能別結果は未提供です。Portのパッケージ化・全機能の受入試験は未検証です。**

## 1. 対象と調査結果

上流: https://github.com/kimata/mod_uploader

対象コミット: `31632a29138b18b7adbf533416a0ec660f1b07ac`。`configure.ac` のバージョン表記は3.2.0です。タグではなく、この固定コミットを基準にしています。上流著作権表示・COPYINGを保持し、本成果物は改変版です。上流へのpush、PR作成、サーバーへの導入は行っていません。

| 構成 | 役割 |
|---|---|
| src/mod_uploader.cpp | Apacheモジュール定義、設定、起動・子プロセス初期化、リクエストフック |
| src/uploader_handler.cpp | 一覧、投稿、削除、ダウンロード、管理、RSS、進捗などのルーティング |
| ApacheResponse / ApacheRequestReader / ApacheResponseWriter | httpdとAPRの入出力処理 |
| RFC1867Parser / MultipartMessageParser | multipart/form-dataと共通MIME解析 |
| UploadItem / UploadItemIO / UploadItemManager | メタデータ、ファイル、共有状態と保存管理 |
| BasicFileWriter / MmapFileWriter | 通常書き込みとmmap書き込み |
| ImageFile | オプションのMagick++サムネイル生成 |
| tmpl / css / img / js | 日本語・英語テンプレート、デザイン、画像、進捗表示 |
| cgi_uploader / stand_uploader | Apacheモジュール以外の実行経路。今回の移植の検証対象外 |

必須の主な依存はApache 2.4の開発用ヘッダー/apxs、APR、C++標準ライブラリ、iconvです。ビルドにはGNU make、Perlと従来の設定検査に使うlibtoolが必要です。サムネイルを有効にするとMagick++が必要になり、gzipを有効にするとzlibが必要になります。Boostは依存していません。

Apache 2.4対応は上流に一部存在しており、ゼロからの2.4化ではありません。古いビルド設定、廃止されたC++所有権クラス、受信データの扱い、接続単位のIP取得などが残っていました。

公式情報では現行のFreeBSDリリースに15.1 / 14.5が掲載されています。これらを対象候補としますが、実機確認したという意味ではありません。

## 2. 実装した変更

### ビルド・API

- C++11を明示し、`auto_ptr` を `unique_ptr` に変更。現在のlibc++で削除されたクラスへの依存を取り除きました。
- `-lstdc++` の固定指定を除去し、選択したC++コンパイラに標準ライブラリの選択を任せます。
- configureからのCFLAGS / CXXFLAGS / CPPFLAGS / LDFLAGSを取り込み、不要な古いGCCオプションを除去しました。
- Clang側の共有モジュールと単独実行／テストリンクについて、オブジェクトの後にライブラリを置きます。
- bashの固定パス、不要なプリコンパイルヘッダー依存、md5sum依存、誤ったlibtool実行可能判定を修正しました。
- 配布済みconfigureにも対応する修正を入れています。configure.acには独自マクロファイルの明示的読み込みと置換変数宣言を追加しました。Autoconfによる再生成そのものは未実行です。
- Apache 2.4では`request_rec.useragent_ip` / `useragent_addr` を使用し、mod_remoteip等が設定するリクエスト単位のアドレスを参照します。信頼するプロキシの設定はApache側で必要です。
- 未設定のhandlerをNULL確認し、C++例外がApacheのCインターフェイスを越えないよう最外層で捕捉します。

### アップロードとセキュリティ

| 調査で確認した問題 | 実装した対策 | 検証範囲 |
|---|---|---|
| 受信バケットのサイズを確認せずmemcpyする | 呼び出し側容量でバケットを分割し、残りを次回へ保持。読取エラーも検査 | 実装を模擬APRで実行 |
| メタデータバケット処理の再帰 | 反復処理へ変更 | 模擬受信テスト |
| バッファの最大位置にNULを書いて領域外になる | 容量とは別に終端1バイトを確保 | 実際のバッファ実装を実行 |
| releaseビルドでは境界検査が無効、erase後に古い文字列末尾が残る | 境界検査を常時有効化、erase後の終端を更新 | 実際のバッファ実装を実行 |
| ファイル本文に含まれる裸のboundaryを区切りと誤認 | CRLF、--、boundary、終端を含む完全な区切りを検査 | 独立した実コードの回帰テスト |
| テキストや最終ファイル断片でサイズ上限を超え得る | 書込み・追加前に残容量で確認し、整数加算のoverflowを回避 | 補助関数の実行＋コード確認。実際のHTTP超過試験は未実施 |
| 項目名の前方一致 | `fileEVIL` 等が `file` と一致しないよう完全一致化 | コード確認のみ |
| パラメータ解析時に終端位置を越えて参照し得る | 空白・名前・等号・値の開始位置を境界内で検査 | コード確認のみ |
| 初期boundary、制御文字、NULを含むヘッダーの扱い | 初期区切り照合、boundary長1～70、ヘッダーNUL拒否 | コード確認のみ |
| ダウンロード／削除パスワードの前方一致 | 完全一致比較に変更 | コード確認のみ |
| 失敗投稿の一時ファイルが残る | リクエストプールのcleanupに削除処理を登録 | FreeBSD/APR上では未実行 |
| 古い無関係な一時ディレクトリ内ファイルも削除する | 自分の投稿一時ファイル名の接頭辞に限定 | コード確認のみ |
| ファイル名に制御文字、区切り、HTML実体参照を使用できる | `/`、制御文字、`&`等を追加拒否。ctypeの符号付きcharも修正 | コード確認のみ |
| 投稿者指定MIMEで同一originの能動文書として配信し得る | octet-stream、attachment、nosniff、sandboxを指定 | HTTP・ブラウザでは未検証 |
| 画像例外のwhat()を破棄後に参照し得る | メッセージをAPRプールにコピーしてからthrow | Magick++では未実行 |
| ブラウザからのクロスサイトPOST | Originがある場合は設定したBaseUrlのoriginと比較。Sec-Fetch-Site cross-siteを拒否 | HTTP・ブラウザでは未検証 |

一時ファイル作成自体は上流がAPRのmktemp / 排他的作成を使っており、それを維持しています。保存ディレクトリは信頼する管理者が用意し、他ユーザーが書き込めないことを前提にします。

## 3. デザイン・機能の維持と変更点

テンプレート、CSS、JavaScript、画像は上流と比較し、改変していないことを確認しました（テキストの改行をLFに統一）。一覧、投稿、進捗、削除、パスワード、RSS、管理画面等の実装を維持しています。ただしブラウザで表示・操作した確認は行えていません。

安全性のため、通常ファイルのインライン表示は添付ダウンロードへ変更しています。サムネイル専用経路は維持しています。ファイル名検証の厳格化とクロスサイトPOST拒否によって、以前受理していた入力を拒否する場合があります。

Portは通常の書込み経路`basic`を選びます。サムネイルは上流の既定と同じく無効で、THUMBNAILオプションで有効にできます。Flash関連ファイルは上流のままですが、現代のブラウザでFlash機能が動くとは扱っていません。

メタデータ構造とバージョン番号は変更していません。ただし既存データの移行試験は未実施です。特に異なるCPU/ABI間でのデータ互換性は保証できません。

## 4. FreeBSD Port候補

`freebsd-port/www/mod_uploader/` にMakefile、distinfo、pkg-descr、pkg-plist、設定例、pkg-message、上流へのパッチを収録しています。

- `USES=apache:2.4 gmake iconv perl5`、固定GitHubコミット、`PATCH_STRIP=-p1`を使用。上流にはCRLFファイルがあるため、pre-patchで対象ファイルをPerlによりLF化してからパッチを適用します。単体パッチを使う場合にも対象ファイルのLF化が必要です。
- distinfoは実際に取得したcodeloadアーカイブのSHA-256とサイズから作成しました。
- `STAGEDIR`を使い、apxsによる本体httpd.confの自動編集を避けています。
- モジュール、既存の日本語／英語テンプレートと静的資産、`.sample`設定をインストールします。
- `/var/db/mod_uploader/{data,file,thumb,temp}` をwww所有・0700とし、DocumentRoot外に保存します。
- Apache設定例は手動Include、ローカル接続のみ許可、admin/mailもローカル限定です。
- アップロード領域をAliasで公開しない設定です。11MiBのHTTP本文上限と10MiBのファイル上限を設定しています。
- THUMBNAIL有効時にはImageMagick7のnox11 flavorを依存とします。
- 保守担当者は未割当で `ports@FreeBSD.org` を設定した候補です。Ports Collectionへの提出・採用済みではありません。

## 5. 実施した検証

環境: Windows、MSYS2 UCRT64のG++ 16.2.0。FreeBSD、Clang、Apacheサーバー、実APRを用いた統合試験ではありません。

| 検査 | 結果 |
|---|---|
| safety_test.cpp: 正常／不正区切り、分割末尾、繰返しデータ、サイズoverflow | 80,012 assertion成功 |
| buffer_test.cpp: 実バッファ実装の最大容量、erase、overflow、reserve | 7 assertion成功 |
| reader_test.cpp: 実受信実装の過大バケット分割、メタデータ、EOS、読取失敗 | 7 assertion成功（APIは模擬） |
| 上記3ファイルのC++11ビルド | `-Wall -Wextra -Werror`で成功 |
| configure / tests/run_native.shのシェル構文検査 | bash -n成功。configureの実行成功とは異なる |
| 固定コミットの実アーカイブをLF正規化後、git apply --check / 適用 | 成功。25個の変更・追加製品ファイルがLF正規化後に修正版と一致 |
| デザイン資産の上流比較 | 改変なし |

コンパイル・実行ログは `native-tests.log`、変更ファイル一覧は `change-manifest.json` です。ネイティブテストは、修正版ソースで `sh tests/run_native.sh` から再実行できます。テスト用ヘッダーはネイティブテストのコンパイルにだけ使用し、製品ビルドには混入させません。ASan/UBSan、ファジング、全multipartパーサーの動的試験は未実施です。

## 6. FreeBSD上での再現・受入手順（未実行）

隔離したFreeBSD 14.5 / 15.1のjailまたはVMで実施してください。既存公開サーバーへの直接適用を想定した手順ではありません。

```sh
# 成果物のwww/mod_uploaderをPortsツリーのローカル領域に配置後
cd /usr/ports/www/mod_uploader
make makesum # 同一distinfoになるか比較。異なる場合は調査する
make clean stage CC=clang CXX=clang++
make check-plist
make stage-qa
# portlint / portfmt / poudriere testport も別途実施する
# テスト用jailへ導入するときのみ
make install
```

`make makesum`はdistinfoを書き換えるので、実行前のファイルを保管し、差分を確認してください。

設定例のUploaderBaseUrlを実際のscheme・host・portへ変更し、必要なMPM、authz_core、alias等がロードされていることを確認します。サンプルをコピーしてhttpd.confから明示的にIncludeし、`apachectl configtest` が成功してからテスト用httpdを起動します。モジュールのロードに成功しただけでは受入完了としません。

ソースを直接ビルドする場合:

```sh
./configure --with-apxs=/usr/local/sbin/apxs \
  --with-aprconf=/usr/local/bin/apr-1-config \
  --with-libtool=/usr/local/bin/libtool --with-writer=basic \
  CC=clang CXX=clang++
gmake LANG=ja_JP.eucJP apache-module
sh tests/run_native.sh
```

実際のapxs等の場所はインストール環境で確認してください。

受入時は次を記録してください。

1. OS/Clang/httpd/APRのバージョン、ビルドログ、ロードエラーとApacheログ。
2. 日本語・英語画面、CSS/画像/進捗の実ブラウザ表示と既存画面との差分。
3. 既知の小ファイルをブラウザから投稿し、一覧・メタデータ・取得したファイルのSHA-256一致を確認。
4. パスワード正解／不正／正しい値に余計な末尾を付けた場合、管理者削除・通常削除。
5. ファイル・テキスト上限ちょうど／1バイト超過、複数パート、本文にboundary文字列を含むファイル、不完全なヘッダー／終端、途中切断。
6. 成功／失敗／途中切断後の一時ファイル、保存領域へ直接HTTPアクセスできないこと、投稿したスクリプトが実行されないこと。
7. 添付配信のHTTPヘッダー、HEAD、Range、RSS、ダウンロードセッション上限。
8. Originの一致・不一致・null・未送信、クロスサイトPOST、リバースプロキシ配下の正しいクライアントIP。
9. preforkから始め、worker/eventを別々に検査。並行投稿・削除、graceful restart、共有メモリ／ロック／権限・ディスク満杯。
10. THUMBNAIL有効／無効、画像破損・巨大画像・資源上限。ImageMagickのcoder/delegateとresource policyを先に制限。
11. 既存データをバックアップした複製で移行・再起動・読み戻しを確認。

## 7. 未解決・未検証事項

- **モジュール全体をClang/FreeBSDでまだコンパイルしていません。追加のコンパイルエラー、ABI/API問題、Port依存解決やステージングの不備が残る可能性があります。**
- FreeBSD Portsのmake、pkg作成、portlint、stage-qa、poudriereは未実行です。
- 実APRのbucket動作、pool cleanup、共有メモリ、ファイルロック、sendfile、mmap、大容量・並行処理は未検証です。
- ImageMagickの画像デコーダは大きな攻撃面です。形式制限・delegate禁止・memory/map/disk/time等のpolicy、実攻撃入力での確認が必要です。今回これらをプロセス全体へ自動適用してはいません。
- パスワードは既存形式の短い平文フィールドです。ハッシュ化、十分な長さへの拡張、試行制限には保存形式を含む追加設計が必要です。今回の完全一致化でこの問題全体が解決したとは扱いません。
- CSRF対策はOrigin / Fetch Metadataによる部分的な強化です。ヘッダーがない要求を許可する互換性を残しており、トークンによる全面的なCSRF対策ではありません。特にadminは公開せず、認証・接続制限を維持してください。
- エラーログへの機微情報、RSS等の全出力コンテキスト、既存データの破損耐性、全ルートの権限検査を網羅したセキュリティ監査ではありません。
- CGI、メール入力、standalone、gzip、Flash、既存の全テスト群は未検証です。共通パーサーを変更しているため、これらを使う場合は独立した回帰試験が必要です。
- FreeBSDでの受入確認が終わるまで、これを「正常動作確認済みの移植版」と表示しないでください。

## 参照した一次資料

- [上流ソース](https://github.com/kimata/mod_uploader)
- [FreeBSD releases](https://www.freebsd.org/releases/)
- [Apache 2.4 API changes](https://httpd.apache.org/docs/2.4/developer/new_api_2_4.html)
- [FreeBSD Porter's Handbook: USES](https://docs.freebsd.org/en/books/porters-handbook/uses/)
- [Ports apache.mk](https://github.com/freebsd/freebsd-ports/blob/main/Mk/Uses/apache.mk)
- [ImageMagick7 Port](https://github.com/freebsd/freebsd-ports/blob/main/graphics/ImageMagick7/Makefile)


## 追補: 提供されたFreeBSDビルドログへの修正

提供ログでは `mod_uploader.cpp:396: error: catch-all handler must come last` により最初のコンパイルが停止していました。配布準備中の処理が例外ハンドラーを重複挿入したことが原因です。Apache 1.x用／2.x用の各関数の末尾にcatch-allを一つだけ残し、配布処理からソースを変更する処理を除去しました。

修正前のApache 2.xハンドラー本体を抽出した試験で同じエラーを再現し、修正後はG++のC++11、Wall/Wextra/Werrorでコンパイル成功、正常要求・別handler・NULL handler・文字列例外・標準例外の5確認が成功しました。`tests/handler_test.py`から再実行できます（Python 3とC++コンパイラが必要）。他の3回帰テストも再実行し成功しました。

提供ログの残る18件はLockerデストラクターからのthrow、Apache設定コールバックの関数型cast、module構造体のflags初期化に関する警告です。この追補では警告を抑制せず、報告された停止エラーの修正に限定しています。FreeBSDでの再ビルドと、後続のコンパイル・リンク・実動作は依然未確認です。

既存の展開済みツリーでは `src/mod_uploader.cpp` を今回の同名ファイルで置き換えてから `gmake` を再実行できます。この変更だけならconfigureの再実行は不要です。Portの上流向けパッチと全体ZIPも同じ修正を反映しています。


## GitHub公開に向けた追補

利用者から「mod_uploader動きました」と報告がありました。過去の節にある未検証表記は、作業環境で直接実行できていない範囲を説明したものです。利用者報告を全機能の検証成功に読み替えてはいません。

ライセンスは上流のCOPYINGを変更せず保持し、PortのLICENSE=ZLIB / LICENSE_FILEを維持しました。MODIFICATIONSとソース内のコメントで改変版を明示し、PortはCOPYINGとMODIFICATIONSもインストールします。

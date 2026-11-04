# Enterprise Linux 対応・検証報告（revision 9）

実施日: 2026-11-04。FreeBSD 改修版 `c37ce9f44f0c66f27464cef026707463a66f8dd9`
を基準に対応しました。元の画面、ルート／サブパス URL、version-4 メタデータ、
認証・CSRF・保存トランザクションは共通です。導入手順は [LINUX-ja.md](LINUX-ja.md)。

## 環境

| 環境 | コンパイラ・Apache | 画像ライブラリ | 検証形態 |
| --- | --- | --- | --- |
| Rocky Linux 10.2 x86_64 | GCC 14.3.1、Apache 2.4.63 | ImageMagick 7.1.2.34 | ユーザー指定の検証機。SELinux Enforcing |
| AlmaLinux 9.8 x86_64 | GCC 11.5.0、Apache 2.4.62 | ImageMagick 6.9.13.58 | 上記ホスト上の公式 AlmaLinux 9 コンテナ |
| FreeBSD 15.1 amd64 | Clang 19.1.7、Apache 2.4.69 | ImageMagick 6.9.13.59 | 既存ホストの独立したソース・データ・loopback Apache |

AlmaLinux は Rocky のカーネルを共有するコンテナ試験であり、AlmaLinux を起動した
実機試験ではありません。通常の HTTP テストは一般ユーザーの別 Apache です。
SELinux の制限下での動作は別途 `httpd_t` ドメインと Enforcing を確認して試験しました。
FreeBSD の既存モジュールは交換せず、前後の SHA-256 が一致しています。

## 問題と修正

1. Apache のビルドディレクトリを `apxs` スクリプトの文字列解析から `apxs -q` に変更。
   テストの Apache／APR／ImageMagick パスもインストール情報から検出します。
2. `--disable-thumbnail` が逆に有効化される設定処理を修正。
   Magick++ の設定コマンドに加えて pkg-config に対応し、設定時にフラグを取得します。
   FreeBSD Port の `PKG_CONFIG_PATH` も configure フェーズへ移動しました。
3. Linux event MPM では glibc の予約領域を fork 先が継承するため、従来の絶対値
   512 MiB の上限が現在の仮想メモリ使用量を下回っていました。strace で、上限設定直後に
   **93 バイトの画像の mmap が ENOMEM になることを再現**しました。
   Linux では継承時点の領域 + 512 MiB に制限し、既存のより厳しい soft/hard 上限を
   維持します。FreeBSD の絶対上限、ImageMagick のキャッシュ制限、CPU・時間・出力制限は
   保持します。1 GiB の予約領域を継承する場合と、管理者のより小さい上限について
   子プロセスを使った回帰テストを追加しました。
4. SELinux では初期値 off の `httpd_setrlimit` が子プロセスの上限設定を拒否しました。
   制限設定の失敗をログへ出すようにし、標準 boolean を有効にする手順を文書化。
   Enforcing を維持し、`httpd_execmem`、`httpd_unified`、任意の外部接続許可は有効にしていません。
5. 古い RPM 定義を更新。Zlib 表示、任意のサムネイル、管理ツール、静的ファイル、
   初期状態では無効な設定例、DocumentRoot 外の apache 所有／0700 の保存領域を同梱。
   RPM 導入による Apache 再起動、データ初期化、移行は行いません。

## 自動試験

以下は各構成での最終的な成功件数です。native の多くは境界値の反復試験やスタブを
使うテストであり、同数の独立した Apache 機能を確認したという意味ではありません。

| 試験 | Rocky 無効 | Rocky 有効 | Alma 有効 | FreeBSD 有効 |
| --- | ---: | ---: | ---: | ---: |
| native 境界値・認証・ルーティング等 | 80,191 | 80,191 | 80,191 | 80,191 |
| メモリ上限のプロセス試験 | 2 | 2 | 2 | 2 |
| ハンドラ（スタブ） | 5 | 5 | 5 | 5 |
| 実 POSIX 保存・障害・復旧 | 655 | 655 | 655 | 655 |
| パスワード移行 | 38 | 38 | 38 | 38 |
| HTTP セキュリティ | 42 | 42 | 42 | 42 |
| HTTPS | 6 | 6 | 6 | 6 |
| 認証・試行制限・プロキシ | 41 | 41 | 41 | 41 |
| 不正入力・競合等 | 20 | 20 | 20 | 20 |
| root／subpath HTTP・HTTPS | 834 | 939 | 939 | 946 |
| 運用・画像・バックアップ復旧 | 54 | 73 | 73 | 73 |
| FreeBSD 設定例 | 20 | 20 | 20 | 20 |
| Linux 設定例 | 20 | 20 | 20 | 20 |

Rocky 無効版のメモリ上限 2 件は RPM の `%check` でも実行しています。
root/subpath の件数には生成されたリンクの検査を含むため、環境によって件数が変わります。
上記の最終試験に失敗はありません。修正前には Linux の画像生成失敗があり、
SELinux 設定前にも生成失敗があったため、初回からすべて成功したという報告ではありません。

追加確認:

- Clang Static Analyzer: 43 翻訳単位、診断 0、コンパイルエラー 0。
- ASan + UBSan: 実 APR／パーサ／リストの 2,118 件成功。Apache 全体や ImageMagick 全体を
  sanitizer 付きで再ビルドした試験ではありません。
- SELinux Enforcing／`httpd_t`: RPM のサムネイル有効版 30 件、無効版 28 件。
  `/` と `/up`、画像・CSS・JS、RSS、アップロード／ダウンロード、認証・CSRF・管理削除を確認。
- FreeBSD amd64 で作成した合成 version-4 データを Rocky x86_64 へ転送し、840 バイトの
  メタデータ読取、ダウンロード／削除パスワード照合、HTTP ダウンロードの 4 件を確認。

## RPM と運用

Rocky 用はサムネイル有効・無効、AlmaLinux 9 用は有効で `rpmbuild -ba` と `%check` を実行。
Rocky ではインストール、構成違いの再インストール、アンインストールを確認しました。
インストール済みのバイナリ・テンプレート・運用ツールでも、Rocky／Alma の有効版は
各 1,032 件（root 939、運用 73、設定例 20）、Rocky 無効版は 908 件
（root 834、運用 54、設定例 20）の HTTP 回帰試験を実施しました。
保存領域に置いたテストファイルは残り、編集した設定例は `.rpmsave` に保存されました。
モジュールだけが除去されることも確認しています。パッケージには自動起動や移行の
scriptlet はありません。RPM はこの検証でローカル作成したもので、配布元署名済み RPM
ではありません。

ビルドには既存由来の GCC 警告（Apache の関数ポインタ変換、固定長フィールドのコピー等）
が残ります。「警告ゼロ」や「脆弱性が存在しない」とは判定していません。

RPM に用いたソース・ビルド設定・テンプレート・静的資産等 273 ファイルは、
作業ツリーと SHA-256 が一致しています（`build-inputs.json`）。3 種類の RPM の
SHA-256 も取得後に照合しました（`artifacts/SHA256SUMS`）。

主な根拠は [検証ログ](validation/linux/) に収録しています。
本番への導入は行っていません。既存サーバーではバックアップ・設定確認・隔離試験後に
管理者が切り替え、問題時は旧モジュール・設定と対応するバックアップを戻してください。

## 未確認事項

- Rocky 9／AlmaLinux 10 の組合せ、Linux 8、他ディストリビューション、ARM・32 bit。
- AlmaLinux の独立カーネル・実機での SELinux／systemd 運用、AlmaLinux のサムネイル無効 RPM。
- 実際の大量データを OS 間で移す運用、異なる CPU ABI／エンディアン間の互換性。
- 長時間の高負荷、実停電・実ディスク故障、外部公開時の TLS・プロキシ・firewalld 構成。
- revision 9 Port の poudriere 再実行。今回の FreeBSD 検証は独立ソースのビルドと実 Apache 試験。

検証機の IPv4 デフォルトゲートウェイが `255.255.0.0` だったため、依存取得の間は
到達確認済みの `10.0.0.1` を一時使用しました。NetworkManager の永続設定は変更していません。

検証終了後、Rocky のテスト RPM と診断用モジュールを除去し、検証用コンテナを停止しました。
標準 httpd サービスは当初どおり inactive、SELinux は Enforcing です。
`httpd_setrlimit` は元の off に戻し、検証用の永続ファイルコンテキスト規則も除去しました。
ビルド依存・ソース・ログ・合成テストデータは検証領域に残しています。

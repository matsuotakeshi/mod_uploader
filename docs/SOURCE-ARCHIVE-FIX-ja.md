# ソースZIPの改行修正（3.2.0_6）

2026-11-02。最初に配布した`mod_uploader-3.2.0_6-source.zip`には配布工程の不備がありました。FreeBSDで`./configure`を実行すると、ファイルが存在し実行権限もあるのに`not found`となります。

## 原因

Windows環境のGitの改行変換がZIP出力にも適用され、`configure`の先頭行が`#! /bin/sh\r\n`になっていました。FreeBSDが解釈するインタープリタ名にCRが残るため起動できません。ビルド補助スクリプトにもCRLFが含まれていました。

前回はPortからのビルドと、別途準備した直接ビルド先で検証しました。完成ZIPについてはCRCと正規化したソースハッシュを検査しましたが、ZIPをそのまま展開して直接ビルドする確認が不足していました。前回の実HTTP試験が成功していても、配布ZIPの直接ビルドを保証できていませんでした。

## 修正

- `.gitattributes`でconfigure、build補助スクリプト、GNUmakefile、シェル・Perl・Pythonスクリプト等の改行をLFに固定しました。
- `tests/source_archive_test.py`を追加し、完成ZIPのCRC、インタープリタ行、実行権限、61個のUnixビルド入力を検査します。
- 配布ZIPを作り直しました。モジュールのC++処理・テンプレート・Portの保存形式・バージョンは変更していません。Portは3.2.0_6のままです。

作り直したZIPは新しいディレクトリへ展開してください。本番の保存データや既存モジュールへ上書き展開する必要はありません。

## 直接ビルド

サムネイルを使う場合の、今回の検証機に合わせた例です。既存の設定条件と依存ライブラリのパスを引き継いでください。

```sh
./configure \
  --with-apxs=/usr/local/sbin/apxs \
  --with-aprconf=/usr/local/bin/apr-1-config \
  --with-libtool=/usr/local/bin/libtool \
  --with-writer=basic \
  --enable-thumbnail \
  --with-mconf=/usr/local/bin/Magick++-config \
  CC=clang CXX=clang++
gmake LANG=ja_JP.eucJP apache-module password-tool
```

引数なしの`./configure`ではサムネイルが無効になります。上記はビルドまでで、本番へのインストールやApache再起動は含みません。[適用・復旧手順](ROOT-DEPLOYMENT-ja.md)に従って別途判断してください。

## 再検証結果

FreeBSD 15.1-RELEASE amd64 / Clang 19.1.7 / Apache 2.4.69 / ImageMagick 6.9.13.50 Q16。新しい専用ディレクトリにZIPを展開し、chmodや改行修正を行わずに検証しました。

| 確認 | 結果 |
| --- | --- |
| 完成ZIPの検査 | 71チェック成功。61個のUnixビルド入力、実行権限、CRC等 |
| `./configure`（引数なし） | 終了コード0。既定のサムネイル無効構成 |
| 上記のサムネイル有効configure | 終了コード0 |
| `gmake LANG=ja_JP.eucJP apache-module password-tool` | 終了コード0。警告は残存、ビルドログに収録 |
| ZIPからビルドしたモジュールの実HTTP/HTTPS | 7構成・946チェック成功。投稿・取得・GIFサムネイル生成、管理認証、CSRF、ルートとサブパス |
| 同モジュールと配布設定例・日本語画面 | 2構成・20チェック成功 |

再検証のチェック数は合計1,037、失敗0です。configure・ビルド工程はこの合計とは別です。Windowsの既定改行設定で作成したZIPも、追加したアーカイブ検査に通過しました。ログは[archive-lf](validation/archive-lf/README.md)に収録しています。

## 再発防止

配布前に、完成ZIPを対象OSで展開して起動・ビルドを検査します。Windows上のアーカイブ作成例:

```sh
git -c core.autocrlf=false archive --format=zip --prefix=mod_uploader-3.2.0_6/ --output=mod_uploader-3.2.0_6-source.zip HEAD
python tests/source_archive_test.py mod_uploader-3.2.0_6-source.zip
```

設定・機能・セキュリティの既存検証範囲は[ルート配置検証報告](ROOT-VALIDATION-ja.md)を参照してください。本番環境の変更、実Certbot更新、ImageMagick 7構成等の未検証事項は引き続き残ります。

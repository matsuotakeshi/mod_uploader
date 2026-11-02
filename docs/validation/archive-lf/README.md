# 配布ZIPの直接ビルド再検証

2026-11-02。[修正報告](../../SOURCE-ARCHIVE-FIX-ja.md)を参照してください。

- `archive-check.log`: FreeBSDでの配布ZIP検査71チェック。
- `configure-default.log`: 展開後、そのまま実行した引数なしのconfigure。終了コード0。
- `configure-thumbnail.log`: ImageMagick 6有効・basic writerを指定したconfigure。終了コード0。
- `build.log`: 同じ展開先からのモジュール・password_toolビルド。終了コード0。既存のコンパイラ警告は残存。
- `root-thumbnail-http.log`: そのビルドを使用した7構成・946チェック。
- `root-samples.log`: 配布設定例と日本語画面の20チェック。
- `shutdown-check.log`: 残存する試験Apache・コアファイルなし。
- `environment.log`: 実測環境。
- `tested-archive-sha256.log`: FreeBSDへ転送した試験用ZIPの識別。最終配布ZIPにはこの試験後の報告・ログを追加するため、ZIP全体のハッシュは異なる。

作業ディレクトリは`<zip-test-dir>`へ置換しています。本番サーバーの設定・モジュール・保存データは変更していません。

# mod_uploader 3.2.0_7 運用・復旧手順

本改修は zlib ライセンスに従った改変版です。画面、ルート `/` とサブパス `/up`、形式4のパスワード、認証・CSRFの設定形式は維持します。保存領域の非公開、本番認証・保護、Certbot更新ドライランは管理者による確認済み事項です。以下のツールが本番停止・交換・初期化を自動実行することはありません。

## バックアップ

`util/storage_backup.py` は FreeBSD / Python 3 用です。Portでは `/usr/local/libexec/mod_uploader/` に入ります。SHA-256でコピー内容を照合し、途中失敗したコピーは `.incomplete-*` として残します。バックアップ先は新規ディレクトリに限り、既存バックアップを上書き・世代削除しません。

全Apacheプロセスを完全停止してから実行します。gracefulによる旧ワーカーの残留中は実施できません。同じ保存領域の `.format-lock` を排他取得し、稼働中のモジュールと競合する場合は拒否します。`--server-stopped` は停止操作ではなく、管理者による停止確認の指定です。

```sh
# 実際の設定先に合わせる。保存先を移動するコマンドではありません。
state=/var/db/mod_uploader
tool=/usr/local/libexec/mod_uploader
snapshot=/srv/backups/mod-uploader/20261103-before-upgrade
python3 "$tool/storage_backup.py" create \
  --data-dir "$state/data" --file-dir "$state/file" \
  --thumb-dir "$state/thumb" --temp-dir "$state/temp" \
  --output "$snapshot" --server-stopped
python3 "$tool/storage_backup.py" verify "$snapshot"
```

バックアップ親ディレクトリは事前に作成し、管理者専用（0700）にします。data内のCSRF鍵も含むため公開領域には置きません。別ホスト・別媒体へ暗号化して複製し、複製先でも `verify` を実行してください。SHA-256照合は破損検出であり、manifestを書き換えられる攻撃者に対する電子署名ではありません。

シンボリックリンク、ハードリンク、デバイス等の特殊ファイルを含むデータセットは拒否します。FreeBSDの `/home` のような管理者指定パスの祖先リンクは正規化します。バックアップ対象同士、または対象と出力先が包含関係にある場合も拒否します。

復旧に必要な旧モジュール、ソースまたはパッケージ、configure引数、Apache設定、独自テンプレートも別途保存してください。通常ファイルのみを集めたリリース保存ディレクトリは `--extra release=/private/release-directory` で同時収録できます。追加対象も他の対象と重複できません。証明書のシンボリックリンクを含むディレクトリはこのツールの対象外です。既存の証明書バックアップ運用を維持します。

## 復元と復旧訓練

```sh
python3 "$tool/storage_backup.py" restore "$snapshot" \
  --destination /srv/recovery/uploader-20261103 --preserve-owner
```

`--preserve-owner` はroot専用です。指定しない場合は復元を実行したユーザーの所有となり、管理者が必要な所有者・権限を設定します。復元先は新規の専用ディレクトリに限定され、元の稼働領域へ直接上書きできません。ルートディレクトリを0700にし、ファイルのsetuid等の特殊許可ビットは復元しません。ACL・ファイルフラグは `cp -a` の範囲で保存しますが、異なるホストのUID/GID対応、ACL・ZFS特性は切替前に確認してください。

1. 新規ディレクトリへの復元と照合を済ませます。
2. 復元したデータだけを参照する、別ポート・loopbackのApacheで一覧、元ファイル取得、パスワード照合、サムネイルを確認します。送信先・公開URLは本番と分離します。
3. 本番への切替時にApacheを完全停止します。切替直前の現行データも別途退避し、バックアップ取得後の投稿が消えないよう扱いを決めます。
4. 旧ディレクトリを残したまま設定の保存先を切り替え、所有者・権限を確認して `apachectl configtest` を実行します。起動後に利用者の操作で確認します。

取得頻度・保管世代・復旧目標は管理者が決めます。例として毎日の停止時間に取得、変更前の追加取得、定期的な別ディレクトリへの復元訓練が可能です。停止を伴うバックアップを無断でcronから実行しないでください。ツールは世代削除を自動化しません。

## 書き込み失敗・中断への対処

新規投稿はデータとメタデータをステージし、その後に容量超過分の既存投稿を移動します。削除予定データは確定前まで戻せる状態で保持します。ファイル更新とディレクトリエントリをfsyncし、例外時は巻き戻します。処理記録は `data/.storage-transaction/` です。

プロセス強制終了やディスク障害で記録が残った場合、次の起動は拒否します。共有メモリのロックを他のワーカーが強制奪取することはありません。待機は短いsleepを挟み、15秒を目安に失敗します。自動再試行やジャーナルの手動削除で処理を継続しないでください。

Apacheを完全停止し、容量不足・I/Oエラー・権限等の原因を直してから確認します。

```sh
python3 "$tool/storage_recover.py" \
  --data-dir "$state/data" --file-dir "$state/file" \
  --thumb-dir "$state/thumb" --temp-dir "$state/temp" --server-stopped
# 上は参照のみ。復旧適用前には必ず新規の救済バックアップを取得します。
python3 "$tool/storage_recover.py" \
  --data-dir "$state/data" --file-dir "$state/file" \
  --thumb-dir "$state/thumb" --temp-dir "$state/temp" --server-stopped \
  --apply --rescue-backup /srv/backups/mod-uploader/20261103-rescue
```

確定前の記録なら巻き戻し、COMMITTED記録があれば確定後の後始末を完了します。指定領域外のパス、リンク、不明な形式・ファイルは拒否します。救済バックアップには未完了状態が含まれるため、通常の完成済みバックアップと区別してください。救済バックアップを別の場所へ復元した場合、記録に残る絶対パスは自動変換しません。元の配置での復旧か、管理者による精査が必要です。

ジャーナルなしで共有ロック所有ワーカーが異常終了した場合も、ログを調査し完全停止・再起動で一覧をディスクから再構築します。電源断、故障したストレージがfsync成功を誤報する場合、外部プロセスによる同時編集までは保証できません。別媒体のバックアップは引き続き必要です。

## 容量・負荷の監視

```sh
python3 "$tool/storage_health.py" \
  --data-dir "$state/data" --file-dir "$state/file" \
  --thumb-dir "$state/thumb" --temp-dir "$state/temp" \
  --min-free-mib 512 --min-free-percent 10
```

終了値0は設定閾値以上かつ未完了記録なし、1は容量等の警告、2は検査失敗です。これは読取専用なのでcron等からの定期実行に使えます。ただし書き込み中に一時的なジャーナルを観測する場合があります。単発警告だけでApacheを止めず、ログと継続時間を確認します。死活監視・通知経路への登録は管理者が行います。

空き容量は既存保存量に加え、受信中の一時ファイルと新規ステージ分を見込みます。満杯になってから旧投稿を先行削除して空ける方式ではありません。大量アップロード時はApacheの `MaxRequestWorkers`、`LimitRequestBody`、OS/ファイルシステム容量も関係します。推奨値は実際のメモリと最大ファイルサイズに合わせて設定します。

`UploaderFileSizeLimit` と `UploaderTotalFileSizeLimit` は従来から **KiB単位** です。1MiBなら `1024`、10MiBなら `10240`、1GiBなら `1048576` です。Apacheの `LimitRequestBody` はバイト単位なので混同しないでください。今回、Port設定例を合計1GiB・1ファイル10MiBに合わせました。既存の本番設定は自動変更しません。負数・0・桁あふれ・数字以外の付いた値は起動時に拒否します。投稿件数・ページ件数は1〜1,000,000です。

低速送信の制限例（VirtualHostまたはサーバー設定）:

```apache
# mod_reqtimeoutがロードされていることを確認して設定します。
RequestReadTimeout header=20-40,MinRate=500 body=20,MinRate=500
```

変更後にconfigtestし、大きいファイル・低速回線の正当な投稿も確認してください。モジュール内のパスワード試行回数と同時照合数制限は維持します。CSRFトークンを負荷制限の代用にはしません。

エラーページの外観を保ちつつ、未知コマンド・不在ID=404、不正入力=400、サイズ超過=413、パスワード不一致=403、投稿間隔=429、ロック待機失敗等=503を返します。内部障害は500です。これまでエラー本文をHTTP 200で受け取っていた自動クライアントは、4xx/5xxの本文も表示できるよう調整してください。通常の完了画面は200のままです。

## 画像処理と依存ライブラリ

サムネイル入力はシグネチャでJPEG/PNG/GIF/WebPを判定し、対象デコーダを指定します。SVG・PDF・MVG等からの生成は行いません。生成できない形式でも通常のアップロード・元ファイル取得は維持します。

画像幅・高さ8192以下、1600万画素以下、ImageMagickメモリ64MiB、map/diskキャッシュ0、スレッド1、内部画像リスト8を上限とします。子プロセスはCPU3秒、壁時計10秒、仮想メモリ512MiB（Linuxではfork時点の継承領域に加えて512MiBまで。管理者設定のより小さい上限は維持）、出力2MiBに制限します。外部delegateとfilterは拒否します。既存の管理者policyによる禁止を解除しません。出力はメタデータを取り除いたGIFです。制限超過時はサムネイルを作らず、元ファイルを保持します。アニメーションや大画像は従来より制限されます。

```sh
python3 "$tool/dependency_audit.py" --output /private/audit/uploader-20261103
```

FreeBSDのVuXMLを専用出力ディレクトリへ取得し、Apache/APR/ImageMagick/Python/libiconvとパッケージ依存先を照合します。終了値0=照合対象の既知警告なし、1=警告あり、2=検査未完了です。`report.json` と個別ログを保存します。ホスト全体の結果は `host-audit.log` です。システムパッケージの更新・削除は行いません。base由来OpenSSLや独自prefixのライブラリはpkg登録外であるため別途確認が必要です。

検証機のImageMagick 6.9.13.50には既知脆弱性があり、上記の資源制限だけで修復したとは扱いません。利用環境でも実際のバージョンと依存先を照合し、修正版へ更新してから有効化してください。更新は隔離検証→全停止時の交換→起動確認の順に行い、本番の既存ライブラリを本作業から自動更新しません。

PortのTHUMBNAIL有効時は `ImageMagick7-nox11>=7.1.2.34` を要求します。古いPortsツリーではこの条件を満たせないため、検証用ツリーとパッケージ情報も更新してください。これは2026-11-03時点の[VuXML警告](https://vuxml.freebsd.org/freebsd/fc4d0a5b-d0c6-11f1-bae2-3497f65b111b.html)への対応であり、将来の警告まで解消する固定値ではありません。

参考: [FreeBSD VuXML ImageMagick6](https://vuxml.freebsd.org/freebsd/fc4d429d-d0c6-11f1-bae2-3497f65b111b.html)、[ImageMagick security policy](https://imagemagick.org/security-policy/)、[FreeBSD Port検証](https://docs.freebsd.org/en/books/porters-handbook/testing/)。

## 更新・ロールバック

新モジュールと運用ツールを別ディレクトリでビルド・確認し、本番適用は管理者が判断します。完全停止中にバックアップを取り、設定とサムネイル有効/無効を維持して交換します。未完了ジャーナルがある状態で旧版を起動しないでください。問題があれば完全停止し、旧モジュール・設定・対応するデータバックアップを戻します。形式4は変わらず、パスワードの再変換は不要です。

具体的な実行結果、試験件数、未検証範囲は `OPERATIONS-VALIDATION-ja.md` に記録します。

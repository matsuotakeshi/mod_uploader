# パスワード保存形式4への安全な移行とCSRF対策

対象: このForkのFreeBSD / Apache 2.4版。既存の稼働データへ自動適用する機能ではありません。

## 変更内容

- 現用メタデータのパスワードは、OpenSSLのPBKDF2-HMAC-SHA256、600,000回、ランダム16バイトsalt、32バイト出力で保存します。saltと回数を含む文字列を128バイトの欄に保存します。
- 保存形式は`4.0.0`です。プログラムの系統はmod_uploader 3.2.0の改修版で、Portのリビジョンは3です。
- 旧形式2/3の16バイト平文欄は、新サーバーでは読み込まず起動時に移行を要求します。無断の自動書換え・平文へのフォールバックはありません。
- 入力パスワードの上限は127バイトです。文字コードの変換や正規化をせず、従来と同じ入力バイト列をハッシュ化します。既存パスワードの再設定は不要です。
- 暗号化ではなく検証用ハッシュです。旧版へ戻すにはバックアップを戻してください。

## 作業前の準備

1. 現在ロードしている旧モジュール、設定、テンプレート、旧パッケージを退避してください。手動導入の場合はLoadModuleが指す実ファイルを保存します。
2. 同じデータ領域を使うApacheと投稿スクリプトをすべて停止します。graceful restartではなく完全停止してください。
3. 新しいモジュール・移行ツールを、旧データを書いた環境と同じCPU/ABI上でビルドします。現在の検証対象はFreeBSD 15 amd64です。異なるABIや未対応サイズは変換せず停止します。
4. バックアップ先の親を用意し、元の全保存領域をもう1組保存できる空き容量を確保します。バックアップ先そのものは存在しないパスを指定してください。
5. 所有者・ACL・フラグを含むバックアップのため、原則rootで移行します。同一ユーザー所有の検証データでは一般ユーザーでも実行できます。バックアップには旧平文パスワードが残るので、外部公開しない場所に保管してください。

Portの移行ツールは `/usr/local/libexec/mod_uploader/password_tool` と `/usr/local/libexec/mod_uploader/migrate_passwords.py` です。手動ビルドはconfigure後に `gmake password-tool` を実行します。

## 実行例

実際のApache設定にある保存先を指定します。以下は標準の設定例です。backupの親ディレクトリは事前に用意します。

```sh
# Apache等を完全停止した後に実行
/usr/local/libexec/mod_uploader/migrate_passwords.py \
  --tool /usr/local/libexec/mod_uploader/password_tool \
  --data-dir /var/db/mod_uploader/data \
  --file-dir /var/db/mod_uploader/file \
  --thumb-dir /var/db/mod_uploader/thumb \
  --temp-dir /var/db/mod_uploader/temp \
  --backup-dir /secure-backups/mod_uploader-before-format4 \
  --server-stopped
```

`--server-stopped`は旧版を停止したことの明示的な確認です。旧版には新しい排他ロックがないため、旧版の停止をツールだけで保証できません。新版は共有ストレージロックを保持し、移行ツールは排他ロックを取るので、新版稼働中や他の移行との同時実行は拒否します。

ツールは次の順に処理します。

1. 保存先の重複・入れ子、シンボリックリンク、ハードリンク、特殊ファイルを検査。
2. `snapshot/data`、`snapshot/file`、`snapshot/thumb`、指定時は`snapshot/temp`をFreeBSDの`cp -a`で保存。バックアップ最上位は0700。
3. 全通常ファイルのSHA-256と一覧を照合し、バックアップを検証。
4. ネイティブABIの変換ツールで全メタデータを別領域へ準備。破損・未対応形式があれば、現用メタデータは置き換えず停止。
5. コピー・準備中に元データが変化していないことを再検査。
6. 起動防止マーカーを置き、メタデータを1件ずつ同一ディレクトリ内のrenameで置換し、fsync・journalを更新。所有者を維持し、メタデータは0600とします。
7. 全件完了後にマーカーを除去。

ユーザーのアップロードファイルやサムネイルの内容は変換しません。旧形式4の正しいデータは再ハッシュせずそのまま扱います。同じバックアップ先の上書きは拒否します。

## 完了・中断時

`journal.json`が`complete`であることと、正しい削除／取得パスワードが使えることを確認してから再公開してください。ブラウザはページを再読み込みし、新しいCookieとフォームのトークンを取得します。

途中で中断した場合は、混在したデータのままサーバーを起動しないでください。`.migration-in-progress`が残ると新版は起動を拒否します。マーカーだけを削除して先へ進めず、バックアップへ戻してからやり直してください。

### 旧版へ戻す

Apache等を停止し、新しい保存ディレクトリを別名で退避します。バックアップの`snapshot/`からdata/file/thumbと必要ならtempを**マージせず、ディレクトリ単位で**元のパスへ戻します。保存しておいた旧モジュール・設定・テンプレートを戻し、所有者・権限を確認してから起動します。移行後に増えた投稿は元のバックアップには含まれません。退避した新データは確認が終わるまで残してください。

バックアップは平文を含むため、検証後もアクセス制限を維持してください。ハッシュ化は、バックアップ内の平文や、利用者自身がファイル本文・コメントへ書いた文字列を消す処理ではありません。

## CSRFトークン

- ランダム256ビットのブラウザセッションCookieに、サーバー秘密鍵によるHMAC-SHA256トークンを結び付けます。トークンには発行時刻と設定BaseUrlを含めて署名し、有効期間は2時間です。
- GETでフォームに`${CSRF_TOKEN}`を出力します。カスタムテンプレートには `name="csrf_token" value="${CSRF_TOKEN}"` のhidden inputを各POSTフォームへ追加してください。
- POSTではCookieとフォームのトークン、またはCookieと`X-CSRF-Token`ヘッダーを検証します。不在・改ざん・期限切れ・別セッション・重複トークンは403です。
- Origin/Referer検査も維持します。トークンがあっても送信元が不正な要求は許可しません。
- HTTPSでは`__Host-mod_uploader_sid`、`Secure`、`HttpOnly`、`SameSite=Strict`、`Path=/`、Domain指定なしを使用します。HTTPの通常Cookieは隔離した検証用です。外部公開にはHTTPSを使用してください。
- 複数タブ、Apacheの複数プロセス、完全再起動に対応します。秘密鍵はdata内の`.csrf-key`に0600で保存し、シンボリックリンク・不正な所有者/権限・壊れた鍵は拒否します。秘密鍵は公開せず、意図的な鍵交換後はページを再読み込みしてください。
- `UploaderBaseUrl`は外部から見える正しいHTTPS URLに設定します。リバースプロキシ配下でも同じです。
- トークンは認証の代わりではありません。admin/mailの接続制限・認証、HTTPS、認証試行・リクエスト量の制限は引き続き必要です。

スクリプトから投稿する場合も、最初にページをGETしてCookieとトークンを取得し、同じCookie、正しいOrigin、X-CSRF-TokenをPOSTで送ってください。メール投稿はフォームではないためヘッダートークンを使用します。CookieやトークンをURL・公開ログへ記録しないでください。

CGI/standalone/Apache 1.xのPOST経路は今回の保護方式に未対応のため拒否します。Flashクライアントもサポート対象ではありません。

## 検証の再実行

```sh
sh tests/run_native.sh
python3 tests/handler_test.py
python3 tests/migration_test.py --tool /path/to/build/src/password_tool
python3 tests/security_http_test.py --build-root /path/to/build \
  --legacy-build-root /path/to/previous-build
python3 tests/security_https_test.py --build-root /path/to/build
```

HTTPテストは専用の一時保存領域と127.0.0.1の空きポートで別Apacheを起動します。稼働Apacheの設定変更や再起動はしません。HTTPSテストは試験用証明書を発行し、その証明書を明示的に信頼して検証します。

今回の実行結果はdocs/validation内に記録します。本番データの移行、全ブラウザ、他ABI、巨大データセット、電源断の実機注入、総当たり耐性・完全なセキュリティ監査を確認したものではありません。

## 根拠

- https://docs.openssl.org/3.0/man3/PKCS5_PBKDF2_HMAC/
- https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html
- https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html

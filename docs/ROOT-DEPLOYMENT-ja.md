# VirtualHostルート・サブパス配置（Portリビジョン6）

2026-11-02。近代化済み3.2.0_5を基にした変更です。保存形式4、パスワード・CSRF・投稿上限・サムネイル生成方式は継続します。特殊なRewriteは必要ありません。

## URLの指定

`UploaderBaseUrl`には利用者から見える絶対HTTP/HTTPS URLを指定します。ルートは`https://up.ysni.org/`または`https://up.ysni.org`、サブパスは`https://example.org/up`または`https://example.org/up/`です。末尾のスラッシュは起動時に除去して統一します。`https://`の区切りは保持します。BaseUrlのパスはApacheのLocationと一致させ、プロキシもそのパスを保持してください。クエリ、フラグメント、ドット区間、パーセント符号化等の曖昧な配置パスは使用できません。

ルートの`/`と`/index`は直接一覧を表示します。サブパスの`/up`は従来どおり307で`/up/`へ移動し、`/up/`と`/up/index`で一覧を表示します。サブパスとDocumentRoot内の実ディレクトリが重なる構成のエラー検査は残しています。`/up`を使う場合は、DocumentRoot直下に同名の実ディレクトリを作らないでください。

## 共通の準備

`mod_uploader.so`をサーバー設定で一度だけ読み込みます。既に読み込んでいる場合は重複させません。

```apache
LoadModule uploader_module /usr/local/libexec/apache24/mod_uploader.so
```

Portは設定を自動有効化しません。`/usr/local/etc/mod_uploader/mod_uploader.conf.sample`はサブパス用、`mod_uploader-root.conf.sample`はルート用です。使う方を`.sample`なしの作業用コピーへ複製し、BaseUrl・公開範囲・保存先を編集してください。両方を同じVirtualHostへ同時に含めないでください。

サンプルには保存先、7種類のテンプレート、上限値、Aliasが含まれます。既存の設定値を優先して引き継いでください。保存先はDocumentRoot・静的Aliasの配下に置かず、data/file/thumb/tempや内部管理ファイルをAliasで公開しないでください。異なるVirtualHostで同じ保存領域を独立したアップローダーとして開かないでください。

## ルート用VirtualHost

次は、証明書の導入が済んでいるサーバー用の例です。ssl、alias、認証関連モジュールを有効にしてください。証明書パスは実際のCertbot構成に合わせます。

```apache
<VirtualHost *:443>
    ServerName up.ysni.org
    DocumentRoot "/usr/local/www/apache24/up.ysni.org"
    SSLEngine on
    SSLCertificateFile "/usr/local/etc/letsencrypt/live/up.ysni.org/fullchain.pem"
    SSLCertificateKeyFile "/usr/local/etc/letsencrypt/live/up.ysni.org/privkey.pem"

    Include "/usr/local/etc/mod_uploader/mod_uploader-root.conf"
</VirtualHost>
```

含める設定の中心は次のとおりです。残りの保存先・テンプレート指定はPortサンプルを使用します。サンプルは`Require local`で始まるので、公開する場合のみこの部分を`Require all granted`へ変更します。

```apache
<Location />
    SetHandler uploader
    Require all granted
    UploaderBaseUrl "https://up.ysni.org/"
    # 保存先、テンプレート、アップロード上限は既存設定を引き継ぐ
</Location>
```

## サブパス用VirtualHost

`mod_uploader.conf`の`UploaderBaseUrl`を`https://example.org/up`に変更し、`<Location /up>`を使用します。サンプル内のLoadModule行は、既に共通設定で読み込んでいる場合やVirtualHost内からIncludeする場合には削除し、読み込みをサーバー設定の一か所へまとめます。

```apache
<VirtualHost *:443>
    ServerName example.org
    DocumentRoot "/usr/local/www/apache24/example.org"
    SSLEngine on
    SSLCertificateFile "/usr/local/etc/letsencrypt/live/example.org/fullchain.pem"
    SSLCertificateKeyFile "/usr/local/etc/letsencrypt/live/example.org/privkey.pem"
    Include "/usr/local/etc/mod_uploader/mod_uploader.conf"
</VirtualHost>
```

## 静的ファイル・Certbotとの共存

`Alias`は保存場所の対応付けです。`<Location />`の`SetHandler uploader`を打ち消すため、静的URLでは`default-handler`を明示します。ルート用サンプルと更新後のサブパス用サンプルに以下を含めています。

```apache
Alias /up_img "/usr/local/share/mod_uploader/img"
Alias /up_css "/usr/local/share/mod_uploader/css"
Alias /up_js  "/usr/local/share/mod_uploader/js"
<LocationMatch "^/up_(img|css|js|swf)(/|$)">
    SetHandler default-handler
    Require all granted
</LocationMatch>
<Directory "/usr/local/share/mod_uploader">
    AllowOverride None
    Options -Indexes -ExecCGI -Includes
    Require all granted
</Directory>
```

SWFを保管している場合は、読み取り専用の専用ディレクトリへ`Alias /up_swf`を別途設定します。PortはFlashクライアントをインストールしません。SWFの静的配信経路を維持するもので、Flashの実行・旧クライアントの認証対応を保証する変更ではありません。

付属テンプレートでは静的ファイルの親URLとして新しい`ASSET_BASE_URL`を使います。ルート配置と`/up`配置ではホスト直下、`/board/up`なら`/board/up_img`等になります。深い階層を使う場合はAliasとLocationMatchもその親階層に合わせます。独自テンプレートの既存`BASE_URL`は利用できますが、`${BASE_URL}/../up_css`等は`${ASSET_BASE_URL}/up_css`へ更新してください。機能リンクは`${BASE_URL}/rss/`等のままで構いません。

HTTP-01方式でCertbotを使っている場合は、そのwebrootの実体と権限を確認し、該当するVirtualHostに例外を追加します。既存のAlias・更新方式を優先してください。DNS-01ならこの例外は不要です。

```apache
<Location /.well-known/acme-challenge/>
    SetHandler default-handler
    Require all granted
</Location>
```

DocumentRootには公開してよいchallengeファイルだけを置き、Directory側もその配信を許可します。アップローダー用のRewriteは不要です。実証明書の発行・更新は今回のモジュール試験の範囲外です。

## 管理画面

サンプルでは管理・メール入口を閉鎖しています。管理画面を使う場合は、ルート配置では`/admin`、サブパス配置では`/up/admin`の既存`Require all denied`ブロックを次のような設定に置き換えてください。Locationの範囲に全管理コマンドが入ることを維持します。

```apache
<Location /admin>
    AuthType Basic
    AuthName "Uploader administration"
    AuthBasicProvider file
    AuthUserFile "/usr/local/etc/apache24/uploader-admin.htpasswd"
    <RequireAll>
        Require ip 192.0.2.10
        Require valid-user
    </RequireAll>
</Location>
```

`192.0.2.10`は説明用です。実際の管理元IPへ置き換え、専用の認証ファイルを使ってください。`htpasswd -cB`で新規作成する場合、既存ファイルを上書きしないよう注意し、パスワードは対話入力します。プロキシ配下では公開側の遮断と信頼プロキシ設定も維持します。`Require local`だけではモジュール側も管理操作を拒否します。認証後の削除にもCSRFが必要です。メール連携は既存の専用認証・CSRF方式を保ち、使用しない場合は閉じたままにします。

## 適用・ロールバック

1. 現在のソース、モジュール、Apache設定、独自テンプレート、data/file/thumb/tempをバックアップします。既存上限値・保存先・サムネイル有効設定を記録します。
2. 本番と分けた場所でビルドします。Portは`make stage check-plist stage-qa package`を使用できます。直接ビルドなら既存のconfigure引数を維持し、サムネイル有効環境では`--enable-thumbnail --with-mconf=/usr/local/bin/Magick++-config`も引き継ぎます。
3. 検証後、管理者が本番適用を判断します。Apacheを完全停止し、新モジュールとテンプレート・設定を適用します。今回の作業自体では本番の交換・再起動を行いません。
4. `apachectl configtest`の成功後に起動し、一覧、画像/CSS/JS、RSS、投稿・取得、サムネイル、管理者認証と未認証拒否を確認します。配置変更前のタブは再読み込みしてください。BaseUrl変更で旧CSRFトークンは無効になります。
5. 問題があれば完全停止し、保存した旧モジュール・設定・テンプレートを戻します。形式4は変わらないので再変換は不要です。データを戻す必要がある場合は対応するバックアップを復元し、検証中や切替後に増えたデータを先に退避してください。

アップロードが上限に達した場合の古いファイル削除など、既存仕様は変わりません。サムネイルの保護・ImageMagickの資源制限など、[セキュリティ運用手順](SECURITY-MIGRATION-ja.md)も継続して適用してください。

Portの既定値と今回作成した検証用パッケージは`THUMBNAIL=off`です。サムネイルを使う既存環境へ、そのまま入れ替えないでください。Portの`THUMBNAIL=on`はImageMagick 7を依存先とします。今回の実画像試験は、検証機に既存のImageMagick 6を利用した直接ビルドで行いました。ImageMagick 7有効のPortパッケージは未検証です。

## 参考

- [Apache Location / SetHandler](https://httpd.apache.org/docs/2.4/mod/core.html#sethandler)
- [Apache Alias](https://httpd.apache.org/docs/2.4/mod/mod_alias.html#alias)

修正内容・テスト件数・実測環境と未検証事項はリポジトリの`docs/ROOT-VALIDATION-ja.md`に記録します。

# Rocky Linux / AlmaLinux での導入

この版は Tetsuya Kimata 氏の mod_uploader 3.2.0 を変更したものです。
元の zlib ライセンス、著作権表示を保持しています。
Linux 対応でも保存形式は version 4、画面・URL・認証方式は FreeBSD 版と共通です。
実測結果と未確認事項は `LINUX-VALIDATION-ja.md` を参照してください。

## ビルド

Enterprise Linux 9 / 10 向けの依存パッケージ例です。コマンドのパスは `apxs`、
`apr-1-config` から検出します。サムネイルなしでは EPEL と ImageMagick は不要です。

```sh
dnf install gcc-c++ make libtool perl httpd httpd-tools mod_ssl httpd-devel apr-devel apr-util-devel openssl-devel
./configure --with-writer=basic --disable-thumbnail
make -j1 LANG=ja_JP.eucJP apache-module password-tool
```

サムネイルを利用する場合は CRB と EPEL を有効にして開発パッケージを導入します。
ImageMagick 6 / 7 の `Magick++-config`、または `pkg-config Magick++` を利用します。

```sh
dnf install dnf-plugins-core epel-release
dnf config-manager --set-enabled crb
dnf install ImageMagick-c++-devel ImageMagick pkgconf-pkg-config
./configure --with-writer=basic --enable-thumbnail
make -j1 LANG=ja_JP.eucJP apache-module password-tool
```

構成を変えるときは別の展開先でビルドしてください。検証は一般ユーザーで実行します。
root では書き込み権限の異常系を正しく検証できません。

```sh
mkdir /tmp/uploader-tests-unique
sh tests/run_integration.sh "$PWD" /tmp/uploader-tests-unique on
# サムネイルなしでは最後の引数を off にする
```

## RPM

`util/mod_uploader.spec.in` は Enterprise Linux 用です。Git checkout の確定した
変更をソースアーカイブにして、一般ユーザーでビルドします。

```sh
dnf install rpm-build redhat-rpm-config python3
mkdir -p "$HOME/rpmbuild/SOURCES" "$HOME/rpmbuild/SPECS"
git archive --prefix=mod_uploader-3.2.0/ --format=tar.gz \
  -o "$HOME/rpmbuild/SOURCES/mod_uploader-3.2.0.tar.gz" HEAD
sed 's/@PACKAGE_VERSION@/3.2.0/g' util/mod_uploader.spec.in \
  > "$HOME/rpmbuild/SPECS/mod_uploader.spec"
rpmbuild -ba --define '_smp_mflags -j1' "$HOME/rpmbuild/SPECS/mod_uploader.spec"
# 有効版: 上記 rpmbuild に --with thumbnail を追加
```

インストール済み RPM の回帰試験には、一般ユーザーで
`sh tests/run_installed_rpm.sh /tmp/専用の既存テストディレクトリ on` を実行します。
別途、検証専用ホストでは管理者として `python3 tests/linux_selinux_test.py` を実行し、
Enforcing／`httpd_t` を確認できます（サムネイル有効版では `--thumbnail` と後述の boolean 設定が必要）。

RPM は Apache モジュールのロード設定を追加しますが、アップローダーの URL は
自動的には有効にしません。Apache の起動・再起動、既存データ移行も行いません。
管理者が設定を確認したうえで `dnf install ./mod_uploader-*.rpm` を実行してください。
導入前から同名モジュールを手動でロードしている場合は重複を解消してください。

| 用途 | RPM の配置 |
| --- | --- |
| モジュール | `/usr/lib64/httpd/modules/mod_uploader.so`（x86_64） |
| ロード設定 | `/etc/httpd/conf.modules.d/20-uploader.conf` |
| 設定例 | `/etc/mod_uploader/mod_uploader{,-root}.conf.sample` |
| テンプレート・画像・CSS・JS | `/usr/share/mod_uploader` |
| 保存領域 | `/var/lib/mod_uploader/{data,file,thumb,temp}` |
| オフライン管理ツール | `/usr/libexec/mod_uploader` |

保存領域は DocumentRoot の外、所有者 `apache`、モード `0700` とします。
RPM は既存ファイルの削除、データ初期化、再帰的な所有者変更を行いません。

## Apache と SELinux

標準の `httpd` サービス、SELinux Enforcing の利用を前提にします。
書き込み領域だけに適切な永続コンテキストを設定します。
すでに同じパスにローカル規則がある場合は `semanage fcontext -l -C` で確認し、
既存規則との整合を取ってください。

```sh
dnf install policycoreutils-python-utils
semanage fcontext -a -t httpd_sys_rw_content_t '/var/lib/mod_uploader(/.*)?'
semanage fcontext -a -t httpd_sys_content_t '/usr/share/mod_uploader(/.*)?'
restorecon -RFv /var/lib/mod_uploader /usr/share/mod_uploader
```

サムネイル有効版では、子プロセスが CPU・メモリ・出力の上限を設定するために
標準の `httpd_setrlimit` boolean も必要です。初期値 off では元画像を保持したまま
サムネイル生成を中止します。Enforcing は維持し、対象の許可だけを設定します。
この boolean は同じ `httpd_t` ドメイン全体に適用されるため、共用 Apache では
他のアプリケーションとの運用方針も確認してください。RPM は自動変更しません。

```sh
getsebool httpd_setrlimit
setsebool -P httpd_setrlimit on
```

配布元の [Apache SELinux ポリシー](https://github.com/fedora-selinux/selinux-policy/blob/rawhide/policy/modules/contrib/apache.te)
にも、この boolean による `setrlimit` の許可が定義されています。

モジュールは標準モジュールディレクトリの `httpd_modules_t` を使用します。
SELinux を無効化したり、Apache の任意の外部接続を許可したりする必要はありません。
独自パスを使う場合、対応するコンテキスト規則も変更します。

`mod_uploader-root.conf.sample` をコピーして専用 VirtualHost 内で Include すると `/`、
`mod_uploader.conf.sample` では `/up` に配置できます。`UploaderBaseUrl` を実際の
HTTPS URL に変更し、公開する場合だけトップの `Require local` を変更します。
末尾の `/` は有無の両方を扱います。Rewrite は不要です。

Alias 配信の `/up_img`、`/up_css`、`/up_js` にはサンプルの
`SetHandler default-handler` を保持してください。サムネイルはモジュール経由で
配信し、保存領域への Alias は作成しないでください。Flash 実行は対応対象外です。

管理画面は初期状態で拒否します。HTTPS を設定し、管理 URL を次のように変更します。
`/up` 配置では `/admin` を `/up/admin` に読み替えてください。

```apache
<Location /admin>
    AuthType Basic
    AuthName "Uploader Administration"
    AuthBasicProvider file
    AuthUserFile /etc/httpd/uploader-admin.htpasswd
    <RequireAll>
        Require ip 192.0.2.10
        Require valid-user
    </RequireAll>
</Location>
```

パスワードファイルは `htpasswd -B` で対話的に作成し、root:apache / 0640 とします。
`restorecon` を実施し、接続元 IP は実際の運用構成に合わせます。プロキシ経由でも
Basic 認証は必要です。外部へのメール転送機能 `/mail` は初期拒否を維持してください。
TLS 証明書、firewalld、リバースプロキシの設定は環境ごとに管理します。

```sh
httpd -t
# 検証してから管理者が実施
systemctl reload httpd
```

## 移行・バックアップ・依存更新

既存データの移行とロールバック手順は `SECURITY-MIGRATION-ja.md`、
`OPERATIONS-ja.md` のオフライン手順を使用します。FreeBSD 固有のパスは上の表に
読み替え、`www` を `apache`、サービス制御を `systemctl` に置き換えます。
バイナリモジュールは OS 間でコピーせず、対象 OS でビルドしてください。
FreeBSD から Linux へ移す場合は UID/GID の違いを確認し、転送後の複製に対してのみ
必要な所有権を調整します。元データと検証済みバックアップは保持してください。

復元は空の別ディレクトリに実行し、検証後に停止中の Apache 設定を切り替えます。
復元先の SELinux コンテキストはバックアップの内容だけに依存せず、
永続規則と `restorecon` で再設定してください。ロールバックは旧モジュール・設定と
対応するバックアップを戻します。パスワードを平文へ逆変換する機能はありません。

`dependency_audit.py` は FreeBSD 専用のため RPM に含めません。Linux では次を
使い、配布元の errata も確認します。DNF に security update がないことだけで
EPEL を含む全依存に脆弱性がないと判定しないでください。

```sh
dnf check-update
dnf updateinfo list --security
rpm -q httpd openssl-libs apr apr-util ImageMagick ImageMagick-c++
```

ImageMagick の管理者ポリシーによって対応形式がさらに制限される場合があります。
モジュール内の寸法・画素数・時間制限、ラスタ形式限定を保持しています。
Linux の event/worker MPM では、glibc が予約した仮想アドレス領域を fork 先が
継承するため、子プロセスの仮想メモリ上限は継承時点の使用量 + 512 MiB とします。
管理者による既存の soft/hard 上限がより小さい場合は引き上げません。
`/proc/self/statm` を読めない場合は生成を中止します。ImageMagick のピクセルキャッシュ
64 MiB、map/disk キャッシュ禁止、CPU 3 秒、壁時計 10 秒、出力 2 MiB も継続します。
これはプロセス全体の常駐メモリが必ず 512 MiB 以下になる保証ではありません。

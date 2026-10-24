PORTNAME=	mod_uploader
PORTVERSION=	3.2.0
PORTREVISION=	5
CATEGORIES=	www
PKGNAMEPREFIX=	${APACHE_PKGNAMEPREFIX}

MAINTAINER=	takeshi@ysni.org
COMMENT=	Apache file uploader with FreeBSD compatibility and security patches
WWW=		https://github.com/matsuotakeshi/mod_uploader

LICENSE=	ZLIB
LICENSE_FILE=	${WRKSRC}/COPYING

LIB_DEPENDS=	libapr-1.so:devel/apr1
BUILD_DEPENDS=	libtool:devel/libtool

USES=		apache:2.4 gmake iconv perl5 ssl python:run
USE_PERL5=	build
USE_GITHUB=	yes
GH_ACCOUNT=	kimata
GH_TAGNAME=	31632a29138b18b7adbf533416a0ec660f1b07ac
PATCH_STRIP=	-p1
GNU_CONFIGURE=	yes
CONFIGURE_ARGS=	--with-apxs=${APXS} \
		--with-aprconf=${LOCALBASE}/bin/apr-1-config \
		--with-libtool=${LOCALBASE}/bin/libtool \
		--with-writer=basic
CPPFLAGS+=	-I${OPENSSLINC}
LDFLAGS+=	-L${OPENSSLLIB}
MAKE_ARGS=	LANG=ja_JP.eucJP
MAKEFILE=	GNUmakefile
ALL_TARGET=	apache-module password-tool
SUB_FILES=	mod_uploader.conf pkg-message
SUB_LIST=	APACHEMODDIR=${APACHEMODDIR}

OPTIONS_DEFINE=	THUMBNAIL
THUMBNAIL_DESC=	Enable ImageMagick raster thumbnails (configure resource policy first)
THUMBNAIL_BUILD_DEPENDS=	Magick++-config:graphics/ImageMagick7@nox11
THUMBNAIL_RUN_DEPENDS=	Magick++-config:graphics/ImageMagick7@nox11
THUMBNAIL_CONFIGURE_ON=	--enable-thumbnail --with-mconf=${LOCALBASE}/bin/Magick++-config

pre-patch:
	${PERL} -pi -e 's/\r\n/\n/g' \
		${WRKSRC}/GNUmakefile.in \
		${WRKSRC}/acinclude.m4 \
		${WRKSRC}/conf/en/apache.conf.in \
		${WRKSRC}/configure \
		${WRKSRC}/configure.ac \
		${WRKSRC}/include/ApacheResponse.h \
		${WRKSRC}/include/FlowController.h \
		${WRKSRC}/include/Locker.h \
		${WRKSRC}/include/MultipartMessageParser.h.in \
		${WRKSRC}/include/MultipartMessageParserBuffer.h \
		${WRKSRC}/include/ReadLocker.h \
		${WRKSRC}/include/UploadItem.h \
		${WRKSRC}/include/UploadItemList.h \
		${WRKSRC}/include/UploadItemManager.h \
		${WRKSRC}/include/WriteLocker.h \
		${WRKSRC}/include/uploader_util.h \
		${WRKSRC}/src/ApacheRequestReader.cpp \
		${WRKSRC}/src/CGIConfigReader.cpp \
		${WRKSRC}/src/CharCodeConverter.cpp \
		${WRKSRC}/src/ConfigReader.cpp \
		${WRKSRC}/src/DirectoryCleaner.cpp \
		${WRKSRC}/src/DownloadFlowController.cpp \
		${WRKSRC}/src/GNUmakefile.dep.in \
		${WRKSRC}/src/GNUmakefile.in \
		${WRKSRC}/src/ImageFile.cpp \
		${WRKSRC}/src/MultipartMessageParser.cpp \
		${WRKSRC}/src/MultipartMessageParserBuffer.cpp \
		${WRKSRC}/src/PostDataChecker.cpp \
		${WRKSRC}/src/PostFlowController.cpp \
		${WRKSRC}/src/RFC1867Parser.cpp \
		${WRKSRC}/src/RFC2822Parser.cpp \
		${WRKSRC}/src/StandConfigReader.cpp \
		${WRKSRC}/src/TemplateLexer.cpp \
		${WRKSRC}/src/TemplateParser.cpp \
		${WRKSRC}/src/UploadItem.cpp \
		${WRKSRC}/src/UploadItemList.cpp \
		${WRKSRC}/src/UploadItemListReader.cpp \
		${WRKSRC}/src/UploadItemManager.cpp \
		${WRKSRC}/src/UploadItemReader.cpp \
		${WRKSRC}/src/UploaderConfig.cpp \
		${WRKSRC}/src/UploaderTemplate.cpp \
		${WRKSRC}/src/mod_uploader.cpp \
		${WRKSRC}/src/uploader_handler.cpp \
		${WRKSRC}/tmpl/admin.htm.in \
		${WRKSRC}/tmpl/download.htm.in \
		${WRKSRC}/tmpl/en/admin.htm.in \
		${WRKSRC}/tmpl/en/download.htm.in \
		${WRKSRC}/tmpl/en/index.htm.in \
		${WRKSRC}/tmpl/en/info.htm.in \
		${WRKSRC}/tmpl/index.htm.in \
		${WRKSRC}/tmpl/index_swf.htm.in \
		${WRKSRC}/tmpl/info.htm.in

post-patch:
	${REINPLACE_CMD} -e '1s|.*|#!${PYTHON_CMD}|' ${WRKSRC}/util/migrate_passwords.py

post-configure:
	${REINPLACE_CMD} -e 's|^SHELL=.*|SHELL=/bin/sh|' ${WRKSRC}/GNUmakefile

do-install:
	${MKDIR} ${STAGEDIR}${PREFIX}/${APACHEMODDIR}
	${INSTALL_LIB} ${WRKSRC}/src/mod_uploader.so ${STAGEDIR}${PREFIX}/${APACHEMODDIR}/
	${MKDIR} ${STAGEDIR}${PREFIX}/libexec/mod_uploader
	${INSTALL_PROGRAM} ${WRKSRC}/src/password_tool ${STAGEDIR}${PREFIX}/libexec/mod_uploader/
	${INSTALL_SCRIPT} ${WRKSRC}/util/migrate_passwords.py ${STAGEDIR}${PREFIX}/libexec/mod_uploader/
	${MKDIR} ${STAGEDIR}${ETCDIR} ${STAGEDIR}${DATADIR}/tmpl/en
	${INSTALL_DATA} ${WRKSRC}/COPYING ${WRKSRC}/MODIFICATIONS ${WRKSRC}/docs/SECURITY-MIGRATION-ja.md ${STAGEDIR}${DATADIR}/
	${INSTALL_DATA} ${WRKDIR}/mod_uploader.conf ${STAGEDIR}${ETCDIR}/mod_uploader.conf.sample
	${INSTALL_DATA} ${WRKSRC}/tmpl/*.htm ${STAGEDIR}${DATADIR}/tmpl/
	${INSTALL_DATA} ${WRKSRC}/tmpl/en/*.htm ${STAGEDIR}${DATADIR}/tmpl/en/
.for dir in css img js
	(cd ${WRKSRC} && ${COPYTREE_SHARE} ${dir} ${STAGEDIR}${DATADIR})
.endfor
	${MKDIR} ${STAGEDIR}/var/db/mod_uploader
.for dir in data file thumb temp
	${MKDIR} ${STAGEDIR}/var/db/mod_uploader/${dir}
.endfor

.include <bsd.port.mk>

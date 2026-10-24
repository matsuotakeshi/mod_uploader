/******************************************************************************
 * Copyright (C) 2007 Tetsuya Kimata <kimata@acapulco.dyndns.org>
 *
 * All rights reserved.
 *
 * This software is provided 'as-is', without any express or implied
 * warranty.  In no event will the authors be held liable for any
 * damages arising from the use of this software.
 *
 * Permission is granted to anyone to use this software for any
 * purpose, including commercial applications, and to alter it and
 * redistribute it freely, subject to the following restrictions:
 *
 * 1. The origin of this software must not be misrepresented; you must
 *    not claim that you wrote the original software. If you use this
 *    software in a product, an acknowledgment in the product
 *    documentation would be appreciated but is not required.
 *
 * 2. Altered source versions must be plainly marked as such, and must
 *    not be misrepresented as being the original software.
 *
 * 3. This notice may not be removed or altered from any source
 *    distribution.
 *
 * $Id: UploadItemReader.cpp 2812 2008-02-23 17:08:39Z svn $
 *****************************************************************************/

#include "Environment.h"

#include <algorithm>

#include "apr_file_info.h"

#include "UploadItemReader.h"
#include "UploadItem.h"
#include "PasswordHash.h"
#include "MetadataSafety.h"
#include "TemporaryPool.h"
#include "TemporaryFile.h"
#include "Message.h"
#include "Macro.h"
#include "SourceInfo.h"

SOURCE_INFO_ADD("$Id: UploadItemReader.cpp 2812 2008-02-23 17:08:39Z svn $");


/******************************************************************************
 * public メソッド
 *****************************************************************************/
UploadItemReader::UploadItemReader(apr_pool_t *pool, const char *data_dir_path,
                                   const char *file_dir_path,
                                   const char *thumb_dir_path)
  : UploadItemIO(pool, data_dir_path, file_dir_path, thumb_dir_path)
{

}

void UploadItemReader::read(apr_size_t item_id, UploadItem *uitem)
{
    const char *uitem_file_path;
    apr_mmap_t *uitem_file_map;
    apr_size_t version;

    TemporaryPool temp_pool(pool_);
    uitem_file_path = get_data_path(temp_pool.get(), item_id);
    File uitem_file(temp_pool.get(), uitem_file_path);

    version = read_and_check(&uitem_file, &uitem_file_map);
    if (version != 4) throw "Legacy metadata: stop Apache and run migrate_passwords.py before startup";
    memcpy(uitem, uitem_file_map->mm, sizeof(UploadItem::header_t));
    if (uitem->get_id() != item_id || !MetadataSafety::valid(*reinterpret_cast<UploadItem::header_t *>(uitem)))
        throw "Invalid metadata strings, identifier or path components";
    if (memchr(uitem->get_remove_pass(),0,ITM_MAX_REMOVE_PASS_SIZE)==NULL ||
        memchr(uitem->get_download_pass(),0,ITM_MAX_DOWNLOAD_PASS_SIZE)==NULL ||
        !PasswordHash::valid(uitem->get_remove_pass()) || !PasswordHash::valid(uitem->get_download_pass()))
        throw "Invalid password metadata";
}

bool UploadItemReader::is_exist_item(apr_size_t item_id) const
{
    const char *uitem_file_path;
    apr_finfo_t info;
    TemporaryPool temp_pool;

    uitem_file_path = get_data_path(temp_pool.get(), item_id);

    return !APR_STATUS_IS_ENOENT(apr_stat(&info, uitem_file_path,
                                          APR_FINFO_MIN, temp_pool.get()));
}

bool UploadItemReader::is_exist_thumbnail(apr_size_t item_id) const
{
    const char *thumbnail_file_path;
    apr_finfo_t info;
    TemporaryPool temp_pool;

    thumbnail_file_path = get_thumb_path(temp_pool.get(), item_id);

    return !APR_STATUS_IS_ENOENT(apr_stat(&info, thumbnail_file_path,
                                          APR_FINFO_MIN, temp_pool.get()));
}

UploadItem *UploadItemReader::read(apr_pool_t *pool, const char *dir_path,
                                 apr_size_t item_id)
{
    UploadItem *uitem;

    UploadItemReader reader(pool, dir_path);

    APR_PALLOC(uitem, UploadItem *, pool, sizeof(UploadItem));
    reader.read(item_id, uitem);

    return uitem;
}


/******************************************************************************
 * private メソッド
 *****************************************************************************/
inline apr_size_t UploadItemReader::read_and_check(File *uitem_file,
                                             apr_mmap_t **uitem_file_map)
{
    uitem_file->open(APR_READ|APR_BINARY);
    *uitem_file_map = uitem_file->mmap(0, 0, APR_MMAP_READ, true);

    return check_format(*uitem_file_map);
}

inline apr_size_t UploadItemReader::check_format(apr_mmap_t *uitem_file_map)
{
    UploadItem *uitem;
    apr_size_t version;

    uitem = AS_UITEM(uitem_file_map->mm);

    // バージョン情報までのデータがあることを確認
    if (uitem_file_map->size < (ITM_MAX_IDENTIFIER_SIZE+ITM_MAX_VERSION_SIZE)) {
        THROW(MESSAGE_UPLOAD_ITEM_FORMAT_INVALID);
    }
    if (UNLIKELY(strncmp(uitem->get_identifier(), PACKAGE_NAME,
                         ITM_MAX_IDENTIFIER_SIZE) != 0)) {
        THROW(MESSAGE_UPLOAD_ITEM_FORMAT_INVALID);
    }

    version = (uitem->get_version())[0] - '0';
    switch (version) {
    case 4:
        if (uitem_file_map->size != sizeof(UploadItem::header_t)) {
            THROW(MESSAGE_UPLOAD_ITEM_FORMAT_INVALID);
        }
        break;
    case 3:
        if (uitem_file_map->size != sizeof(UploadItem::header_ver3_t))
            THROW(MESSAGE_UPLOAD_ITEM_FORMAT_INVALID);
        break;
    case 2:
        if (uitem_file_map->size != sizeof(UploadItem::header_ver2x_t)) {
            THROW(MESSAGE_UPLOAD_ITEM_FORMAT_INVALID);
        }
        break;
    default:
        THROW(MESSAGE_PROGRAM_TOO_OLD);
    }

    return version;
}

// Local Variables:
// mode: c++
// coding: utf-8-dos
// End:

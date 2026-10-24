// Altered source: validate before eviction and serialize capacity changes.
/******************************************************************************
 * Copyright (C) 2007 Tetsuya Kimata <kimata@acapulco.dyndns.org>
 *
 * All rights reserved.
 *
 * This software is provided 'as-is', without any express or without_lockied
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
 * $Id: UploadItemManager.cpp 2907 2009-01-14 12:56:44Z svn $
 *****************************************************************************/

#include "Environment.h"

#include <cstdlib>
#include <cstring>
#include <algorithm>
#include <memory>

#include "apr_time.h"
#include "apr_file_info.h"

#include "UploadItemManager.h"
#include "UploadItem.h"
#include "MetadataSafety.h"
#include "UploadItemList.h"
#include "UploadItemIterator.h"
#include "ThumbnailList.h"
#include "TemporaryPool.h"
#include "ReadLocker.h"
#include "WriteLocker.h"
#include "Message.h"
#include "Macro.h"
#include "SourceInfo.h"

using namespace std;

SOURCE_INFO_ADD("$Id: UploadItemManager.cpp 2907 2009-01-14 12:56:44Z svn $");

#ifdef DEBUG
#include <iostream>
#endif

#define AS_UITEM_MANAGER(pointer)   reinterpret_cast<UploadItemManager *>(pointer)

#ifdef DEBUG
#define REQUIRE_MANAGER_LOCKED()                                \
    do {                                                        \
        if (!ReadLocker::is_locked(lock_)) {       \
            throw MESSAGE_MANAGER_SHOULD_LOCKED                 \
                " (" __FILE__ ":" APR_STRINGIFY(__LINE__) ")";  \
        }                                                       \
    } while (0)
#else
#define REQUIRE_MANAGER_LOCKED()
#endif

const apr_size_t UploadItemManager::SYNC_FACTOR = 32;
const apr_size_t UploadItemManager::SYNC_LIMIT  = 200;

namespace {
// Let the compiler align time/size fields in the process-shared region.
struct ManagerSharedState {
    apr_atomic_t lock;
    apr_time_t mtime;
    apr_size_t age;
};
}

apr_time_t UploadItemManager::get_mtime() const
{
    ReadLocker manager_locker(lock_);
    return *mtime_;
}

void UploadItemManager::update_mtime(apr_time_t mtime)
{
    WriteLocker manager_locker(lock_);
    if (mtime > *mtime_) *mtime_ = mtime;
}


/******************************************************************************
 * public メソッド
 *****************************************************************************/
apr_size_t UploadItemManager::add(apr_pool_t *pool,
                                  const char *file_name, const char *file_mime,
                                  apr_uint64_t file_size,
                                  const char *file_digest,
                                  const char *file_temp_path,
                                  const char *remove_pass,
                                  const char *download_pass,
                                  const char *comment, const char *code_pat,
                                  const char *ip_address)
{
    apr_size_t item_id;

    item_id = add_impl(pool, file_name, file_mime, file_size, file_digest,
                       file_temp_path, remove_pass, download_pass, comment,
                       code_pat, ip_address);

    sync_all_item_by_catches(pool);

    return item_id;
}

void UploadItemManager::remove(apr_pool_t *pool, UploadItem *uitem)
{
    remove_impl(pool, uitem);

    sync_all_item_by_catches(pool);
}

void UploadItemManager::sync_all_item(apr_pool_t *pool, apr_size_t sync_limit)
{
    UploadItem::header_t *header;
    apr_size_t synced_count;
    WriteLocker manager_locker(lock_);

    REQUIRE_MANAGER_LOCKED();

    synced_count = 0;
    for (apr_size_t i = 0; i < item_list_->size(); i++) {
        header = item_list_->get_by_index(i);

        if (header->is_need_sync) {
            item_writer_.write_data(pool, header);

            if (++synced_count == sync_limit) {
                break;
            }
        }
    }
}

UploadItem *UploadItemManager::get_item(apr_pool_t *pool, apr_size_t item_id)
{
    UploadItem *uitem;

    ReadLocker manager_locker(lock_);
    REQUIRE_MANAGER_LOCKED();

    APR_PALLOC(uitem, UploadItem *, pool, sizeof(UploadItem));
    memcpy(uitem, item_list_->get_by_id(item_id), sizeof(UploadItem));

    return uitem;
}

apr_file_t *UploadItemManager::get_item_file(apr_pool_t *pool,
                                             UploadItem *expected,
                                             bool is_sendfile_enabled)
{
    const apr_size_t item_id = expected->get_id();
    const char *file_path;
    apr_file_t *file;
    UploadItem *uitem;
    // Protect identity validation, opening the payload, and mutable counters.
    WriteLocker manager_locker(lock_);

    REQUIRE_MANAGER_LOCKED();

    uitem = AS_UITEM(item_list_->get_by_id(item_id));

    file_path = UploadItemIO::get_file_path(pool, file_dir_path_, uitem);

    if (!MetadataSafety::same_identity(*AS_UITEM_H(uitem), *AS_UITEM_H(expected)))
        THROW(MESSAGE_LIST_ID_INVALID);

    if (apr_file_open(&file, file_path,
                      APR_READ | (is_sendfile_enabled ? APR_SENDFILE_ENABLED : 0),
                      APR_OS_DEFAULT, pool) != APR_SUCCESS) {
        THROW(MESSAGE_FILE_OPEN_FAILED);
    }
    uitem->increment_download_count();
    uitem->update_atime();
    return file;
}

void UploadItemManager::update_atime(apr_size_t item_id)
{
    WriteLocker manager_locker(lock_);
    REQUIRE_MANAGER_LOCKED();

    AS_UITEM(item_list_->get_by_id(item_id))->update_atime();
}

UploadItemManager *UploadItemManager::get_instance(apr_shm_t *shm,
                                                   apr_pool_t *pool,
                                                   const char *data_dir_path,
                                                   const char *file_dir_path,
                                                   const char *thumb_dir_path,
                                                   UploadItemList *item_list,
                                                   ThumbnailList *thumbnail_list,
                                                   apr_time_t mtime)
{
    UploadItemManager *item_manager;

#ifdef DEBUG
    if (apr_shm_size_get(shm) != get_memory_size()) {
        THROW(MESSAGE_SHM_SIZE_INVALID);
    }
#endif

    APR_PALLOC(item_manager, UploadItemManager *, pool,
               sizeof(UploadItemManager));

    new(item_manager) UploadItemManager(shm, pool, data_dir_path,
                                        file_dir_path, thumb_dir_path,
                                        item_list, thumbnail_list, mtime);

    return item_manager;
}

void UploadItemManager::child_init(apr_shm_t *shm, UploadItemList *item_list,
                                   ThumbnailList *thumbnail_list)
{
    ManagerSharedState *state = static_cast<ManagerSharedState *>(apr_shm_baseaddr_get(shm));
    lock_ = &state->lock;
    mtime_ = &state->mtime;
    age_ = &state->age;

    item_list_ = item_list;
    thumbnail_list_ = thumbnail_list;
}

apr_size_t UploadItemManager::get_memory_size()
{
    return sizeof(ManagerSharedState);
}

void UploadItemManager::check_finalize_state(UploadItemManager *item_manager)
{
    if (ReadLocker::is_locked(item_manager->lock_)) {
        THROW(MESSAGE_MANAGER_SHOULD_NOT_LOCKED);
    }
}


/******************************************************************************
 * private メソッド
 *****************************************************************************/
UploadItemManager::UploadItemManager(apr_shm_t *shm, apr_pool_t *pool,
                                     const char *data_dir_path,
                                     const char *file_dir_path,
                                     const char *thumb_dir_path,
                                     UploadItemList *item_list,
                                     ThumbnailList *thumbnail_list,
                                     apr_time_t mtime)
  : pool_(pool),
    data_dir_path_(data_dir_path),
    file_dir_path_(file_dir_path),
    thumb_dir_path_(thumb_dir_path),
    item_writer_(pool, data_dir_path, file_dir_path, thumb_dir_path)
{
    child_init(shm, item_list, thumbnail_list);

    *lock_ = 0;
    *mtime_ = mtime;
    *age_ = 0;
}

apr_size_t UploadItemManager::add_impl(apr_pool_t *pool,
                                       const char *file_name,
                                       const char *file_mime,
                                       apr_uint64_t file_size,
                                       const char *file_digest,
                                       const char *file_temp_path,
                                       const char *remove_pass,
                                       const char *download_pass,
                                       const char *comment,
                                       const char *code_pat,
                                       const char *ip_address)
{
    apr_size_t item_id;
    apr_size_t item_index;
    UploadItem *uitem;
    apr_time_t current_time;

    // Validate and hash before any deletion or shared-list lock.
    current_time = apr_time_now();
    uitem = UploadItem::get_instance
        (pool, 0, 0, file_size, current_time, ip_address,
         file_name, file_mime, file_digest, remove_pass, download_pass, comment, code_pat);
    if (!item_list_->can_fit(file_size)) THROW(MESSAGE_RFC1867_FILE_SIZE_TOO_LARGE);

    {
        WriteLocker manager_locker(lock_);

        REQUIRE_MANAGER_LOCKED();

        create_item_id_index(&item_id, &item_index);
        remove_files_locked(pool, file_size);
        reinterpret_cast<UploadItem::header_t *>(uitem)->id = item_id;
        reinterpret_cast<UploadItem::header_t *>(uitem)->index = item_index;

        if (item_writer_.write(uitem, file_temp_path)) {
            thumbnail_list_->add(uitem->get_id());
        }
        item_list_->add(uitem);

        set_mtime(current_time);
    }

    return item_id;
}

void UploadItemManager::remove_impl(apr_pool_t *pool, UploadItem *uitem)
{
    WriteLocker manager_locker(lock_);

    REQUIRE_MANAGER_LOCKED();

    UploadItem *current = AS_UITEM(item_list_->get_by_id(uitem->get_id()));
    if (!MetadataSafety::same_identity(*AS_UITEM_H(current), *AS_UITEM_H(uitem)))
        THROW(MESSAGE_LIST_ID_INVALID);

    // 処理の順番を変えるとまずい
    item_writer_.remove(pool, uitem);
    item_list_->remove(uitem->get_id());
    thumbnail_list_->remove(uitem->get_id());

    set_mtime(apr_time_now());
}

void UploadItemManager::remove_files(apr_pool_t *pool, apr_uint64_t file_size)
{
    WriteLocker manager_locker(lock_);
    remove_files_locked(pool, file_size);
}

void UploadItemManager::remove_files_locked(apr_pool_t *pool, apr_uint64_t file_size)
{
    REQUIRE_MANAGER_LOCKED();
    if (!item_list_->can_fit(file_size)) THROW(MESSAGE_RFC1867_FILE_SIZE_TOO_LARGE);
    while (item_list_->is_full(file_size)) {
        if (item_list_->size() == 0) THROW(MESSAGE_BUG_FOUND);
        UploadItem *old_uitem = AS_UITEM(item_list_->get_by_index(item_list_->size()-1));
#ifdef REMOVE_UNPOPULAR
        for (apr_size_t i = 0; i < item_list_->size(); ++i) {
            UploadItem *candidate = AS_UITEM(item_list_->get_by_index(i));
            if (candidate->get_atime() < old_uitem->get_atime()) old_uitem = candidate;
        }
#endif
        item_writer_.remove(pool, old_uitem);
        thumbnail_list_->remove(old_uitem->get_id());
        item_list_->remove(old_uitem->get_id());
    }
}

void UploadItemManager::create_item_id_index(apr_size_t *item_id,
                                             apr_size_t *item_index) const
{
    UploadItem::header_t *header;

    *item_id = static_cast<apr_size_t>(apr_time_sec(apr_time_now()));

    if (item_list_->size() == 0) {
        *item_index = 1;
        return;
    }

    apr_size_t max_id = 0, max_index = 0;
    for (apr_size_t i = 0; i < item_list_->size(); ++i) {
        header = item_list_->get_by_index(i);
        max_id = std::max(max_id, header->id);
        max_index = std::max(max_index, header->index);
    }
    if (max_id == static_cast<apr_size_t>(-1) || max_index == static_cast<apr_size_t>(-1))
        throw "Upload identifier exhausted";
    if (*item_id <= max_id) *item_id = max_id + 1;
    *item_index = max_index + 1;
}

void UploadItemManager::sync_all_item_by_catches(apr_pool_t *pool)
{
    bool synchronize;
    {
        WriteLocker manager_locker(lock_);
        synchronize = (*age_ % SYNC_FACTOR) == 0;
        ++*age_;
    }
    if (synchronize) {
        sync_all_item(pool, SYNC_LIMIT);
    }
}

// Local Variables:
// mode: c++
// coding: utf-8-dos
// End:

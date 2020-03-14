from enum import IntEnum
from .base_cache import MetadataCache
from .minio_cache import MinioCache
from .fs_cache import FsCache
from ..config import global_config

class CacheMgr:

    class CacheType(IntEnum):
        NOT_CACHED = 0
        LOCAL = 1
        REMOTE = 2

    fs_cache: FsCache = FsCache()
    def __init__(self):
        if global_config.remote_cache_enable:
            self.minio_cache = MinioCache()

    def open_cache(self, cache_hash) -> MetadataCache:
        try:
            if global_config.local_cache:
                return self.fs_cache.open_cache(cache_hash)
            else:
                raise FileNotFoundError
        except FileNotFoundError:
            if global_config.remote_cache_enable:
                return self.minio_cache.open_cache(cache_hash)
            raise FileNotFoundError

    def save_cache(self, cache_hash, metadata_cache: MetadataCache):
        if global_config.local_cache:
            self.fs_cache.save_cache(cache_hash, metadata_cache)
        if global_config.remote_cache_enable:
            self.minio_cache.save_cache(cache_hash, metadata_cache)

    def _get_cache(self, deps_hash, targets):
        ret = False
        if global_config.local_cache:
            ret = self.fs_cache._get_cache(deps_hash, targets)
        if ret is False:
            if global_config.remote_cache_enable:
                ret = self.minio_cache._get_cache(deps_hash, targets)
                if ret is True:
                    return CacheMgr.CacheType.REMOTE
        else:
            return CacheMgr.CacheType.LOCAL
        return CacheMgr.CacheType.NOT_CACHED

    def _save_cache(self, deps_hash, targets, local_only=False):
        if global_config.local_cache:
            self.fs_cache._save_cache(deps_hash, targets)
        if local_only:
            return
        if global_config.remote_cache_enable:
            self.minio_cache._save_cache(deps_hash, targets)

    def gc(self):
        self.fs_cache.gc()

import shutil
import hashlib
import pickle
import os
from os.path import join
from subprocess import check_output
from .base_cache import MetadataCache
from umake.config import UMAKE_BUILD_CACHE_DIR
from umake.colored_output import out
from umake.utils.fs import fs_lock, fs_unlock, get_size_KB
from umake.utils.timer import Timer
from umake.config import global_config


class FsCache:

    def __init__(self):
        pass

    def open_cache(self, cache_hash) -> MetadataCache:
        cache_src = join(UMAKE_BUILD_CACHE_DIR, "md-" + cache_hash.hex())
        with open(cache_src, "rb") as metadata_file:
            metadata = pickle.load(metadata_file)
            return metadata

    def save_cache(self, cache_hash, metadata_cache: MetadataCache):
        cache_src = join(UMAKE_BUILD_CACHE_DIR, "md-" + cache_hash.hex())
        with open(cache_src, "wb") as metadata_file:
            pickle.dump(metadata_cache, metadata_file, protocol=pickle.HIGHEST_PROTOCOL)

    def _get_cache(self, deps_hash, targets):
        if deps_hash is None:
            return False
        cache_src = join(UMAKE_BUILD_CACHE_DIR, deps_hash.hex())
        try:
            for target in targets:
                f = hashlib.sha1(target.encode("ascii")).hexdigest()
                src = join(cache_src, f)
                shutil.copyfile(src, target)
                shutil.copymode(src, target)
        except FileNotFoundError:
            shutil.rmtree(cache_src, ignore_errors=True)
            return False

        return True

    def _save_cache(self, deps_hash, targets):
        cache_dst = join(UMAKE_BUILD_CACHE_DIR, deps_hash.hex())
        fd, lock_path = fs_lock(cache_dst)
        if fd == None:
            return
        try:
            shutil.rmtree(cache_dst, ignore_errors=True)
            os.mkdir(cache_dst)
            for target in targets:
                dst = join(cache_dst, hashlib.sha1(target.encode("ascii")).hexdigest())
                tmp_dst = f"{dst}.tmp"
                # do "atomic" copy, in case the copy is interferred
                shutil.copyfile(target, tmp_dst)
                shutil.copymode(target, tmp_dst)
                os.rename(tmp_dst, dst)
        finally:
            fs_unlock(fd, lock_path)

    def gc(self):
        def remove(path):
            """ param <path> could either be relative or absolute. """
            if os.path.isfile(path):
                os.remove(path)  # remove the file
            elif os.path.isdir(path):
                shutil.rmtree(path)  # remove dir and all contains
            else:
                raise ValueError("file {} is not a file or dir.".format(path))

        with Timer("done cache gc") as timer:
            cache_dir_size_KB = get_size_KB(UMAKE_BUILD_CACHE_DIR)
            high_thresh = cache_dir_size_KB * 1.1
            low_tresh = global_config.local_cache_size * 1024 * 0.6

            if global_config.local_cache_size * 1024 > high_thresh:
                return

            fd, lock_path = fs_lock(UMAKE_BUILD_CACHE_DIR)
            if fd == None:
                out.print_fail(f"\tcahce: {UMAKE_BUILD_CACHE_DIR} is locked")
                return
            try:
                cache_entry_size = 0
                cache_dir = check_output(['ls', '-lru', '--sort=time', UMAKE_BUILD_CACHE_DIR]).decode('utf-8')
                for cache_line in cache_dir.splitlines():
                    try:
                        _, _, _, _, _, _, _, _, cache_entry_name = cache_line.split()
                        cache_entry_full_path = join(UMAKE_BUILD_CACHE_DIR, cache_entry_name)
                        remove(cache_entry_full_path)
                        cache_entry_size = get_size_KB(UMAKE_BUILD_CACHE_DIR)
                        if cache_entry_size < low_tresh:
                            break
                    except ValueError:
                        pass
                timer.set_postfix(f"freed {int((cache_dir_size_KB - cache_entry_size) / 1024)}MB")
            finally:
                fs_unlock(fd, lock_path)
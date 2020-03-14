import certifi
import urllib3
import hashlib
import os
import pickle
import io
from os.path import join
from stat import S_IMODE
from minio import Minio, error  # takes 0.1 seconds, check what to do
from minio.helpers import MAX_POOL_SIZE
from umake.cache import base_cache
from umake.cache.base_cache import MetadataCache
from umake.config import global_config
from umake.colored_output import out


class MinioCache(base_cache.Cache):

    def __init__(self):
        self.n_timeouts = 0
        ca_certs = certifi.where()
        http = urllib3.PoolManager(
                timeout=1,
                maxsize=MAX_POOL_SIZE,
                        cert_reqs='CERT_REQUIRED',
                        ca_certs=ca_certs,
                        retries=urllib3.Retry(
                            total=3,
                            backoff_factor=0.5,
                            status_forcelist=[500, 502, 503, 504]
                        )
            )

        self.mc = Minio(global_config.remote_hostname,
                        access_key=global_config.remote_access_key,
                        secret_key=global_config.remote_secret_key,
                        secure=False,
                        http_client=http)

    def _increase_timeout_and_check(self):
        self.n_timeouts += 1
        if self.n_timeouts >= 3:
            out.print_fail(f"remote cache timedout {self.n_timeouts} time, disabling remote cahce")
            global_config.remote_cache_enable = False

    def open_cache(self, cache_hash)->MetadataCache:
        cache_src = "md-" + cache_hash.hex()
        try:
            metadata_file = self.mc.get_object(bucket_name=global_config.remote_bucket, object_name=cache_src)
            metadata = pickle.loads(metadata_file.read())
            return metadata
        except (urllib3.exceptions.ReadTimeoutError, urllib3.exceptions.MaxRetryError, urllib3.exceptions.ProtocolError):
            self._increase_timeout_and_check()
            raise FileNotFoundError
        except error.RequestTimeTooSkewed:
            out.print_fail("Time on your host not configured currectlly, remote-cache is disabled")
            global_config.remote_cache_enable = False
            raise FileNotFoundError
        except error.NoSuchKey:
            raise FileNotFoundError

    def save_cache(self, cache_hash, metadata_cache: MetadataCache):
        cache_src = "md-" + cache_hash.hex()
        md = pickle.dumps(metadata_cache, protocol=pickle.HIGHEST_PROTOCOL)
        try:
            self.mc.put_object(bucket_name=global_config.remote_bucket, object_name=cache_src, data=io.BytesIO(md), length=len(md))
        except (urllib3.exceptions.ReadTimeoutError, urllib3.exceptions.MaxRetryError, urllib3.exceptions.ProtocolError):
            self._increase_timeout_and_check()
        except error.RequestTimeTooSkewed:
            out.print_fail("Time on your host not configured currectlly, remote-cache is disabled")
            global_config.remote_cache_enable = False

    def _get_chmod(self, src):
        if hasattr(os, 'chmod'):
            st = os.stat(src)
            return st.st_mode
        else:
            return None

    def _set_chmod(self, dst, st_mode):
        os.chmod(dst, S_IMODE(st_mode))

    def _get_cache(self, deps_hash, targets):
        if deps_hash is None:
            return False
        cache_src = deps_hash.hex()
        try:
            for target in targets:
                f = hashlib.sha1(target.encode("ascii")).hexdigest()
                src = join(cache_src, f)
                obj = self.mc.fget_object(bucket_name=global_config.remote_bucket, object_name=src, file_path=target)
                st_mode = int(obj.metadata["X-Amz-Meta-St_mode"])
                self._set_chmod(target, st_mode)
        except KeyError:
            # some cases with minio that .metadata["X-Amz-Meta-St_mode"] is not exists
            # the file will be pushed again after compilation
            out.print_fail("metadata not exists")
            return False
        except error.NoSuchKey:
            return False
        except (urllib3.exceptions.ReadTimeoutError, urllib3.exceptions.MaxRetryError, urllib3.exceptions.ProtocolError):
            self._increase_timeout_and_check()
            return False
        except error.RequestTimeTooSkewed:
            out.print_fail("Time on your host not configured currectlly, remote-cache is disabled")
            global_config.remote_cache_enable = False
            return False

        return True

    def _save_cache(self, deps_hash, targets):
        cache_dst = deps_hash.hex()
        # fd, lock_path = fs_lock(cache_dst)
        # if fd == None:
        #     return
        try:
            # shutil.rmtree(cache_dst, ignore_errors=True)
            # os.mkdir(cache_dst)
            for target in targets:
                dst = join(cache_dst, hashlib.sha1(target.encode("ascii")).hexdigest())
                file_attr = {"st_mode": self._get_chmod(target)}
                self.mc.fput_object(bucket_name=global_config.remote_bucket, object_name=dst, file_path=target, metadata=file_attr)
        except (urllib3.exceptions.ReadTimeoutError, urllib3.exceptions.MaxRetryError, urllib3.exceptions.ProtocolError):
            self._increase_timeout_and_check()
        except error.RequestTimeTooSkewed:
            out.print_fail("Time on your host not configured currectlly, remote-cache is disabled")
            global_config.remote_cache_enable = False
        finally:
            # fs_unlock(fd, lock_path)
            pass

    def get_cache_stats(self):
        bucket_size = 0
        n_objects = 0
        for obj in self.mc.list_objects(bucket_name=global_config.remote_bucket, recursive=True):
            if obj.is_dir:
                continue
            bucket_size += obj.size
            n_objects += 1
        print(f"bucket size {int(bucket_size / 1024 / 1024)}MB, n_objects {n_objects}")

    def clear_bucket(self):
        for obj in self.mc.list_objects(bucket_name=global_config.remote_bucket, recursive=True):
            self.mc.remove_object(bucket_name=global_config.remote_bucket, object_name=obj.object_name)
        self.get_cache_stats()
import os
from os.path import join

CONFIG_ENV_PREFIX = 'UMAKE_CONFIG_'

# Local cache
ROOT = os.environ.get(f'{CONFIG_ENV_PREFIX}_ROOT', os.getcwd())
UMAKE_BUILD_CACHE_MAX_SIZE_MB = int(os.environ.get(f'{CONFIG_ENV_PREFIX}LOCAL_CACHE_SIZE', '1500'))

# General
UMAKE_MAX_WORKERS = 8
UMAKE_ROOT_DIR = join(ROOT, ".umake")
UMKAE_TMP_DIR = join(UMAKE_ROOT_DIR, "tmp")
UMAKE_BUILD_CACHE_DIR = join(UMAKE_ROOT_DIR, "build-cache")
UMAKE_DB = join(UMAKE_ROOT_DIR, "db.pickle")

class Config:
    def __init__(self):
        self.json_file = None
        self.interactive_output = False
        self.local_cache = True
        self.targets = []
        self.variant = "default"
        self.compile_commands = False
        self.verbose = True

        self.remote_cache_config = True  # how user configured
        # the next is result of `remote_cache_config` and if configured
        self.remote_cache_enable = False
        self.remote_hostname = None
        self.remote_access_key = None
        self.remote_secret_key = None
        self.remote_bucket = None


global_config = Config()
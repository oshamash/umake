import os
from os.path import join

CONFIG_ENV_PREFIX = 'UMAKE_CONFIG_'

# Remote cache
MINIO_URL = os.environ.get(f'{CONFIG_ENV_PREFIX}MINIO_URL', "localhost:9000")
MINIO_ACCESS_KEY = os.environ.get(f'{CONFIG_ENV_PREFIX}MINIO_ACCESS_KEY', 'umake')
MINIO_SECRET_KEY = os.environ.get(f'{CONFIG_ENV_PREFIX}MINIO_SECRET_KEY', 'umakeumake')
MINIO_BUCKET_NAME = os.environ.get(f'{CONFIG_ENV_PREFIX}MINIO_BUCKET_NAME', "umake-build-cache")

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
        self.remote_cache = True
        self.local_cache = True
        self.targets = []
        self.variant = "default"
        self.compile_commands = False
        self.verbose = True


global_config = Config()
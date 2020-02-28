import os

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
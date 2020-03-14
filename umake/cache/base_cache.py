from abc import ABC, abstractmethod

class MetadataCache:
    def __init__(self, deps):
        self.deps = deps


class Cache(ABC):

    @abstractmethod
    def open_cache(self, cache_hash)->MetadataCache:
        """
        Get an object from the cache using a given hash.

        :param cache_hash: The key of the object to get
        :return: The resulting element from cache.
        """
        pass

    @abstractmethod
    def save_cache(self, cache_hash, metadata_cache: MetadataCache):
        """
        Save a given object into the cache.

        :param cache_hash:     The hash to use for storing the element in the cache.
        :param metadata_cache: The object to store in the cache.
        """
        pass

    @abstractmethod
    def get_cache_stats(self):
        """
        Get stats on the number of artifacts in the cache.
        """
        pass

    @abstractmethod
    def clear_bucket(self):
        """
        Delete all the artifacts in the cache.
        Mainly used for clean variants.
        """
        pass
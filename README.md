UMake
=====
**Blazing Fast. Sub second Modification detection. Just a few seconds for cached compilation**

![dpdk build](doc/images/dpdk-build/dpdk-build.gif)

Overview
--------
UMake is a build system that building your projects.
Influenced by [`tup`](http://gittup.org/tup/). With the features below your compilation speed will be on average dramatically reduced, either after branch change either with your `CI` builds.


#### `Local cache`
many base libraries in your project rarely changed, why recompile them over and over again. Local cache reduce compilation times and remote cache access.

#### `Remote cache`
If someone already compiled most of the libraries in your project, use those results.

#### `Auto dependency discovery`
makes your life easier to create build scripts no matter what your tool is: `gcc`, `protoc`, `docker build` ...


[Detailed overview](doc/overview.md)

[Cache System](doc/cache.md)

[UMakefile](doc/umakefile.md)

Install
-------
```
git clone https://github.com/grisha85/umake.git
cd umake
pip install .
```

Running example
---------------
```
git clone https://github.com/grisha85/umake.git
cd umake
docker build -t umake  .
docker run --rm -it -v`pwd`/example:/example -w/example umake bash
umake --no-remote-cache
./hello_world
```

UMake configuration
-------------------
This section lists all the various configurations that umake supports

| Variable name                  | Description                                                |
|--------------------------------|------------------------------------------------------------|
| UMAKE_CONFIG_MINIO_ACCESS_KEY  | An access key (username) for minio that umake should use   |
| UMAKE_CONFIG_MINIO_SECRET_KEY  | A secret key (password) for minio that umake should use    |
| UMAKE_CONFIG_MINIO_BUCKET_NAME | The name of the bucket to use in minio                     |
| UMAKE_CONFIG_MINIO_URL         | A url to use to access minio                               |
| UMAKE_CONFIG_LOCAL_CACHE_SIZE  | The maximal size in bytes of the cache to store locally    |
| UMAKE_CONFIG_ROOT              | The root directory in which all umake files will be stored |

Real Life Examples
------------------
[DPDK build](doc/dpdk-build.md)


Talking about UMake:
--------------------
This section includes link to various places around the web that reason about umake.
We believe that by reviewing questions and opinions that other people wrote about umake one can learn more about it.
So without further ado is here is the list:

* [DriveNets blog](https://drivenets.com/blog/the-inside-story-of-how-we-optimized-our-own-build-system/)
* [Reddit r/bazel](https://www.reddit.com/r/bazel/comments/fa084s/how_we_optimised_our_build_system_using_umake/)
* [Reddit r/cpp](https://www.reddit.com/r/cpp/comments/f9yjxn/how_we_optimised_our_build_system_using_umake/)
* [Reddit r/gcc](https://www.reddit.com/r/gcc/comments/faiqum/how_we_optimised_our_build_system_using_umake/)

Have another story to share about umake? just open a PR with a change to this list and we'll merge it in.

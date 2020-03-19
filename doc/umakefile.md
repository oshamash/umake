

UMakefile
---------
## Rule `:`

A single `command` is generated for this rule

`:` source `|` manual-deps `>` cmd `>` target

`manual-deps` - targets the this target depends on, helps keep a correct build order

`cmd` - bash command

`target` - the output of the command


`{filename}` - full path filename of the source `/my/path/filename.a`

`{dir}` - directory containing the source `/my/path/`

`{noext}` - filename without extension `filename`

`{target}` - expanded target `helloworld.a`

Example:
```
: *.o > gcc {filename} -o {target} > helloworld.a
```

#### Recursive Source `**`
recursice dependencies are support
```
root\
  a\
    a.a\
      a.a.a
      a.a.b
      a.b.a
    a.b\
      a.b.a
      a.b.b
  b\
    b
```
* `root/**` -> (`a.a.a`, `a.a.b`, `b`)
* `root/a/**/*.b` -> (`a.a.b`, `a.b.b`)

#### Manual Dependency `|`
In order to maintain a correct build order (that is executed in parallel), there are use cases where manual dependecy is needed. for example: if there are `generated headers` (like when using `protobuf`) that are being later used by another `command` to generate a different target.


## Rule `:foreach`
Same as `:` but will create `command` for each `source` file existing on filesystem (like when we match the pettern *.o in the example above)

## Macro `!`
Macros are expanded immediately (like using `#define X "hello"` in c/cpp)
Macros can accept input parameters (again, similar to using c/cpp macros)

Example:
```
!c(includes, flags) : gcc -g -O2 -Wall -fPIC -c {filename} $includes $flags -o {target} > {dir}/{noext}.o
```
#### Default values
`Macro` supports default values, by default they are `""`:
```
!c(includes, flags=-O3) : gcc -g -O2 -Wall -fPIC -c {filename} $includes $flags -o {target} > {dir}/{noext}.o
```
now `!c` can be called as following:
```
!c(-Iinclude)       # includes = -Iinclude, flags=-O3
!c(-Iinclude, -O0)  # includes = -Iinclude, flags=-O0
!c()                # includes = "", flags=-O3
```
## Const `$`
Consts are like macros, and can be used to parametrize calls to macros
Example:
```
$libs = -lpthread
!so($libs)
```

## Config `[<config_item>:<config_value>]`
Configs allow to configure and changing umake execution.

#### `workdir`
Default: \<root>

Change the current working directory.
`relative paths` will now be relative to the new working dir.
`Absoulte paths` will now be relative to the `root` (the directory where UMakefile exists).

Example:
Relative path `my_dir_a/my_dir_b` will be evaluated as `<workdir>/my_dir_a/my_dir_b`.
However `/my_dir_a/my_dir_b` will be evaluated as `<root>/my_dir_a/my_dir_b` *regardless* of what our `workdir` is.

The following rules are similar:

```
: src/packages/a > gcc > src/packages/b
```
```
[workdir:src/packages]
: a > gcc > b
```
Return to root
```
[workdir:/]
```

#### `variant`

Defult: "default"

The ability to generate diffrent variants from the same sources. For example: debug/release compilations. variant `terminated` with a `newline`
```
# varaint is terminated with newline
[variant:default]
$cflags = -O3

[variant:debug]
$cflags = -O0

: my.c > !c($cflags) > my.o
```
now compile with `umake` for default variant
```
umake
```
or
```
umake --variant debug
```
for `debug` variant.

#### `include`
Default: -

include another `UMakefile` into the current one.
```
[include:somedir/umakefile]
```
will open and parse `somedir/umakefile` in the current working dir context.

#### `remote cache`
Default: None

Environment: UMAKE_CONFIG_REMOTE_CACHE

configure remote cache
```
[remote_cache:<remote-cache-type> <uri> <access-key> <secret-key> <bucketname> <permission>]
```

**remote-cache-type** - minio

**hostname** - hostname:port

**access-key** - access key (user name)

**secret-key** - secret key (password)

**bucketname** - bucketname

**permission** - ro (read-only)/ rw (read/write)


#### `local cache size`
Default: 1500MB

Environment: UMAKE_CONFIG_LOCAL_CACHE_SIZE

configure local cache size
```
[local_cache_size:<MB>]
```
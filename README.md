UMake
=====

Overview
--------
UMake is a build system that building your projects.  
influenced by [`tup`](http://gittup.org/tup/). 

UMakefile
---------
## Rule `:`
`:` target-source | manual-deps `>` cmd `>` target

`manual-deps` - targets the this tule depends on, in order to keep a correct build order  
`cmd` - bash command  
`target` - the output of the command  
  
`{filename}` - full path filename of the source `/my/path/filename.a`  
`{dir}` - directory of the source `/my/path/`  
`{noext}` - filename without extension `filename`  
`{target}` - expanded target `helloworld.a`  



Example:
```
: *.o > gcc {filename} -o {target} > helloworld.a
```

## Rule `:foreach`
Same as `:` but will create `cmd` for each `target-source` file will be found on filesystem

## Macro `!`
Macros are expanded immediatlly (like `#define X "hello"` in c/cpp)  
Macros can accepted parameters

Example:
```
!c(includes, flags) = gcc -g -O2 -Wall -fPIC -c {filename} $includes $flags -o {target} > {dir}/{noext}.o  
```
## Const `$`
Consts are like macros, and can be used to parametrize calls to macros
Example:
```
$libs = -lpthread
!so($libs)
```

# Cache System

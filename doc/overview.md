UMake Overview
==============
Since a lot of the core concepts from tup apply to umake it is highly recommended to read the following:

* http://gittup.org/tup/ex_dependencies.html
* http://gittup.org/tup/make_vs_tup.html


Why UMake
---------
- Fast modification detection (sub second even for large projects)
- More parallelism due to DAG (more details later)
- Fast re-compilation, with built-in cache (local-cache, remote-cache)


My First UMakfile
-----------------
`a.c`:
```
#include "dep_a.h"
#include "stdio.h"

int
main()
{
    printf("hello\n");
    return 0;
}
```


`UMakefile`:
```
: a.c > gcc -c {filename} {target} > a.o
```
the rule above parsed to the following command
```
gcc -c a.c a.o
```

### Graph of the rule above
![ ](./images/overview/1.png)


### Graph after executing the rule
![ ](images/overview/2.png)

Now if any of the nodes (`a.c`, `dep_a.h`, `gcc -c a.c a.o` or `a.o`) will be modified, `a.o` will be regenerated. umake use both timestamps and hashes to check for modifications.

Targets as dependencies
----------------------
`b.c`:
```
#include "a.pb-c.h"
#include "stdio.h"

int
main()
{
    printf("hello\n");
    return 0;
}
```
Lets have another rule that generates header which will be used by other another rule.

`UMakefile`:
```
: a.proto > protoc {filename} > a.pb-c.h a.pb-c.c
: b.c > gcc -c {filename} {target} > b.o
```
first rule above is generating header `a.pb-c.h` that `b.c` is including.
### Graph after parsing the rules
![ ](images/overview/3.png)


Now we have copmilation ordering issue. `b.o` might be generated before `a.pb-c.h` because nothing enforce the order between and `b.o` and `a.pb-c.h`.

When running the above `UMakefile`, an error will be reported. This is because second rule using target of the the first rule internally (to generate `b.o`, `a.pb-c.h` is needed)

### Manual Dependency: `|`
In order to fix this order issue we need to tell `umake` that generating `b.o` should come only after `a.pb-c.h` is generated. We would use `| a.pb-c.h` for that.

`UMakefile`:
```
: a.proto > protoc {filename} > a.pb-c.h a.pb-c.c
: b.c | a.pb-c.h > gcc -c {filename} {target} > b.o
```

### Graph after parsing the above UMakefile
![ ](images/overview/4.png)


:foreach rule
--------

```
: src/src_a.c > compile.sh {filename} {target} > src/src_a.o
: src/src_b.c > compile.sh {filename} {target} > src/src_b.o
: src/src_c.c > compile.sh {filename} {target} > src/src_c.o
: src/src_d.c > compile.sh {filename} {target} > src/src_d.o
```
can be changed to:
```
:foreach src/*.c > compile.sh {filename} {target} > {dir}/{noext}.umake.o
```
`:foreach` works exactlly like `:` (macros, vars, manual dependencies.)

Macros and Variables
--------------------
The above statement might repeated many times in UMakefile. so macros can be used in order to make life easier.

```
!c(includes, flags) : gcc -c {filename} {target} $includes $flags > {dir}/{noext}.umake.o

: src/*.c > !c(-Iinclude, -O3)
```

`c` - macro name

`includes`, `flags` - arguments to marcro


**The above can be also used with variables:**
```
!c(includes, flags) : compile.sh {filename} {target} $includes $flags > {dir}/{noext}.umake.o

$includes = -Iinclude
$flags = -O3
: src/*.c > !c($includes, $flags)
```

Compiling specific target
-------------------------
```
umake lib/libmy_lib.so
```
In this case only the subraph of `lib/libmy_lib.so` will be recompiled

Variants
--------
```
$debug_flags = -O3

[variant:debug]
$debug_flags = -O0

$includes = $debug_flags
: src/*.c > !c($debug_flags, )
```
Now if compiled with `umake` the `-O3` flags will be passed. If compiled with `umake -v debug` the `-O0` flags will be passed.

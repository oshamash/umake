
# Build DPDK in 9 seconds
[`DPDK`](https://www.dpdk.org/) is an open source project for fast packet processing. `umake` can compile it in `9` seconds:

![dpdk build](images/dpdk-build/dpdk-build.gif)

## Setup

- VM with 6 cpus / `Intel(R) Xeon(R) Gold 6138 CPU @ 2.00GHz` host
- UMakefile was auto generated after ninja (verbose) compilation 
- prepare tests with:
```
git clone https://github.com/grisha85/dpdk.git
cd dpdk
make prepare
```
## Results
| compilation                    	| time (seconds) 	| command           	|
|--------------------------------	|----------------	|-------------------	|
| ninja (original build)                          	| 160            	| make ninja        	|
| umake - uncached               	| 274            	| make umake [1]    	|
| umake - local cache            	| `9`              	| make umake-local  	|
| umake - remote cache(over lan) 	| 14             	| make umake-remote 	|

[1] strace has huge performance penalty


## Remarks and Conclusions

- This is not full port of DPDK compilation to `umake`.
- In most compilations there are limited number of files that are being changed, so `umake` can increase dramatically compilation speed. This is especially true for CI builds.

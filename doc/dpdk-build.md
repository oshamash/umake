
# Build DPDK in 9 seconds
[`DPDK`](https://www.dpdk.org/) is an open source project for fast packet processing. `umake` can compile it in `9` seconds:

![dpdk build](images/dpdk-build/dpdk-build.gif)

## Setup

- VM with 6 cpus / `Intel(R) Xeon(R) Gold 6138 CPU @ 2.00GHz` host
- prepare tests with:
```
git clone https://github.com/grisha85/dpdk.git
cd dpdk
make prepare
```
## Results
| compilation                    	| time (seconds) 	| command           	| comments 	|
|--------------------------------	|----------------	|-------------------	|----------	|
| ninja                          	| 160            	| make ninja 
| ninja null build                         	| 0.054            	| make ninja        	|          	|
| umake - uncached               	| 274            	| make umake        	| [1]      	|
| umake null build               	| 0.9            	| make umake        	|       	|
| umake - local cache            	| `9`            	| make umake-local  	|          	|
| umake - remote cache(over lan) 	| 14             	| make umake-remote 	|          	|

1. strace has huge performance penalty

## How the port to `umake` was made
- output of verbose `ninja` compilation was saved to a file: [ninja compilation output](https://github.com/grisha85/dpdk/blob/master/ninja)
- this output was parsed with a [python script](https://github.com/grisha85/dpdk/blob/master/parse_ninja.py) to `UMakefile` 
- 

## Remarks

- This is not full port of DPDK compilation to `umake`.
- This is especially true for CI builds.

# Conclusion
**In most compilations there are limited number of files that are being changed, so `umake` can increase dramatically compilation speed (11-16 times faster).**


.PHONY: test enter

test: 
	docker run --rm --privileged -it -v`pwd`/test:/test -w/test -vumake:/umake grisha85/umake python3.6 test.py

enter:
	docker run --rm --privileged -it -v`pwd`/test:/test -w/test -vumake:/umake grisha85/umake bash


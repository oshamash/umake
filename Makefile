

.PHONY: test enter

build-docker:
	docker build -t grisha85/umake .

test: 
	docker run --rm --privileged -it -v`pwd`/test:/test -w/test -v`pwd`:/umake grisha85/umake python3.6 test.py

enter:
	docker run --rm --privileged -it -v`pwd`/test:/test -w/test -v`pwd`:/umake grisha85/umake bash 


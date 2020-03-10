

.PHONY: test enter

IMAGE=grisha85/umake:1

build-docker:
	docker build -t ${IMAGE} .

test: 
	docker run --rm --privileged -it -v`pwd`:/umake -w/umake ${IMAGE} bash -c 'cd test && python3.6 test.py'

enter:
	docker run --rm --privileged -it -v`pwd`:/umake -w/umake ${IMAGE} bash 


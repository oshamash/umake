FROM ubuntu:18.04
RUN apt-get update -y
RUN apt-get install -y python3.6 build-essential python3-pip libxml2-dev zlib1g-dev strace vim
RUN apt-get install -y git
ADD . /umake
RUN pip3 install ipdb
RUN pip3 install -e /umake

# for tests
RUN apt-get install -y libprotobuf-c0-dev protobuf-c-compiler
RUN pip3 install coverage

FROM ubuntu:18.04
RUN apt-get update -y
RUN apt-get install -y python3.6 build-essential python3-pip libxml2-dev zlib1g-dev strace vim wget
ADD . /umake
RUN pip3 install -e /umake

RUN pip3 install ipdb coverage pyflakes

RUN wget https://dl.min.io/server/minio/release/linux-amd64/minio && chmod +x ./minio && mv ./minio /usr/bin

# for tests
RUN apt-get install -y libprotobuf-c0-dev protobuf-c-compiler

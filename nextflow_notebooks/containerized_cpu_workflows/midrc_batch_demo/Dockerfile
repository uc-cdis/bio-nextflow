FROM quay.io/cdis/containers:gen3-amazonlinux-base-AL2023fix
USER root

RUN yum update && yum install -y \
    python3 \
    python3-pip \
    g++ \
    libgsl* \
    wget && \
    rm -rf /var/lib/yum/lists/*

COPY ../../images/batch_cpu_demo /utils
WORKDIR /utils

RUN pip install setuptools
RUN pip install gen3
RUN pip install pylibjpeg
RUN pip install pylibjpeg-libjpeg
RUN pip install -r requirements.txt


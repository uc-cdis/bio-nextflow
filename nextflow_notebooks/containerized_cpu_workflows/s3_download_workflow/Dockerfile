FROM public.ecr.aws/u5x5h6w3/nextflow-approved/public:amazonlinux-base

RUN yum update && yum install -y \
    python3 \
    python3-pip \
    wget && \
    rm -rf /var/lib/yum/lists/*

COPY ./utils /utils
COPY ./requirements.txt /tmp/requirements.txt
WORKDIR /utils

RUN pip install setuptools
RUN pip install gen3
RUN pip install -r /tmp/requirements.txt
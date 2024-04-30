FROM public.ecr.aws/u5x5h6w3/nextflow-approved/public:amazonlinux-base

RUN yum update && yum install -y \
    python3 \
    python3-pip \
    wget && \
    rm -rf /var/lib/yum/lists/*

# set workdir
WORKDIR /app/

COPY ./utils /app
COPY ./requirements.txt /app/

# install requirements
RUN pip install -r requirements.txt

# switch to /app dir
RUN cd /app

# symlink python to python3
RUN ln -s /usr/bin/python3 /usr/bin/python

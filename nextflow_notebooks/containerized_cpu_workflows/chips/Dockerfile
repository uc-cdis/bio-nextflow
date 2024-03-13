FROM broadinstitute/gatk:latest as gatk 
FROM quay.io/cdis/containers:gen3-amazonlinux-base-AL2023fix

RUN yum update && yum install -y \
    python3 \
    python3-pip \
    g++ \
    libgsl* \
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

# Download human reference genome

RUN wget https://api.gdc.cancer.gov/data/254f697d-310d-4d7d-a27b-27fbf767a834

# symlink python to python3
RUN ln -s /usr/bin/python3 /usr/bin/python

#copy gatk over
COPY --from=gatk /gatk /app/gatk

# install java
RUN yum install java-17-amazon-corretto -y

FROM python:3.9.14
USER root

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    python3 \
    python3-pip \
    g++ \
    libxml2-dev \
    libssl-dev \
    libcurl4-openssl-dev \
    libssh2-1-dev \
    zlib1g-dev \
    openssl \
    gdebi-core \
    libgsl* \
    libudunits2-dev \
    libgs-dev \
    wget && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY . /utils
WORKDIR /utils

RUN pip install -r requirements.txt


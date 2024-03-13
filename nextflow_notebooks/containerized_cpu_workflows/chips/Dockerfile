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

RUN wget https://api.gdc.cancer.gov/data/254f697d-310d-4d7d-a27b-27fbf767a834 -O GRCh38.d1.vd1.fa.tar.gz

# symlink python to python3
RUN ln -s /usr/bin/python3 /usr/bin/python

#copy gatk over
COPY --from=gatk /gatk /app/gatk

# install java
RUN yum install java-17-amazon-corretto -y

# install samtools
RUN yum install tar -y
RUN yum install bzip2 -y
RUN yum install zlib-devel -y
# note that bz2 is needed for cram files,also lzma. disabling for now
RUN wget https://github.com/samtools/samtools/releases/download/1.19.2/samtools-1.19.2.tar.bz2 \
    && tar jxf samtools-1.19.2.tar.bz2 \
    && cd samtools-1.19.2 \
    && ./configure --without-curses --disable-bz2 --disable-lzma\
    && make -j 2 \
    && mv samtools /usr/local/bin/samtools \
    && cd .. \
    && rm -r samtools-1.19.2/ \
    && rm samtools-1.19.2.tar.bz2

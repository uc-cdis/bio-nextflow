FROM quay.io/cdis/containers:gen3-amazonlinux-base-AL2023fix
USER root

RUN yum update && yum install -y \
    python3 \
    python3-pip \
    g++ \
    libgsl* \
    wget && \
    rm -rf /var/lib/yum/lists/*

COPY ./utils .
COPY ./9063a470-699b-495b-9c4f-0feaba4120c0 .
COPY ./GRCh38.d1.vd1.fa .

RUN pip install numpy
RUN pip install pandas
RUN pip install requests

ENV APPS_ROOT /apps
RUN mkdir -p ${APPS_ROOT}

###############################################
#GATK = 'gatk/4.1.3.0'

ENV GATK_VERSION 4.1.3.0

ENV GATK_HOME ${APPS_ROOT}/gatk/${GATK_VERSION}

ENV GATK_LOCAL_JAR ${GATK_HOME}/gatk-package-${GATK_VERSION}-local.jar
ENV GATK_SPARK_JAR ${GATK_HOME}/gatk-package-${GATK_VERSION}-spark.jar
ENV GATK_JAR ${GATK_HOME}/gatk-package-${GATK_VERSION}-local.jar
ENV PATH ${GATK_HOME}:${PATH}

RUN wget https://github.com/broadinstitute/gatk/releases/download/${GATK_VERSION}/gatk-${GATK_VERSION}.zip \
        && mkdir ${APPS_ROOT}/gatk \
        && unzip gatk-${GATK_VERSION}.zip \
        && mv gatk-${GATK_VERSION} ${APPS_ROOT}/gatk/${GATK_VERSION} \
        && rm gatk-${GATK_VERSION}.zip

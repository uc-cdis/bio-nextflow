FROM broadinstitute/gatk:4.5.0.0 as base



RUN yum update && yum install -y \
    python3-pip \
    wget \
    g++ \
    libgsl* && \
    rm -rf /var/lib/yum/lists/*


RUN pip install numpy
RUN pip install pandas
RUN pip install requests


FROM quay.io/cdis/containers:gen3-amazonlinux-base-AL2023fix AS base_image

COPY ./utils .
COPY test_data .

# Install miniconda \
#ENV CONDA_DIR /opt/conda
#RUN wget --quiet https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O ~/miniconda.sh && \
#    /bin/bash ~/miniconda.sh -b -p /opt/conda

# Put conda in path so we can use conda activate
#ENV PATH=$CONDA_DIR/bin:$PATH

#RUN conda create -n gatk4 -c conda-forge -c bioconda gatk4





#ENV APPS_ROOT /apps
#RUN mkdir -p ${APPS_ROOT}

###############################################
#GATK = 'gatk/4.1.3.0'

#ENV GATK_VERSION 4.1.3.0

#ENV GATK_HOME ${APPS_ROOT}/gatk/${GATK_VERSION}

#ENV GATK_LOCAL_JAR ${GATK_HOME}/gatk-package-${GATK_VERSION}-local.jar
#ENV GATK_SPARK_JAR ${GATK_HOME}/gatk-package-${GATK_VERSION}-spark.jar
#ENV GATK_JAR ${GATK_HOME}/gatk-package-${GATK_VERSION}-local.jar
#ENV PATH ${GATK_HOME}:${PATH}

#RUN wget https://github.com/broadinstitute/gatk/releases/download/${GATK_VERSION}/gatk-${GATK_VERSION}.zip \
#        && mkdir ${APPS_ROOT}/gatk \
#        && unzip gatk-${GATK_VERSION}.zip \
#        && mv gatk-${GATK_VERSION} ${APPS_ROOT}/gatk/${GATK_VERSION} \
#        && rm gatk-${GATK_VERSION}.zip

FROM nvcr.io/nvidia/dgl:25.08-py3
LABEL author="Jozef Michal Bukas"
LABEL brief="Graph repository with system for domain evaluation based on the mutual relationships"
EXPOSE 8000

WORKDIR /workspace

COPY ../../src ./app/src
COPY ../../requirements.txt ./requirements.txt

RUN set -eux && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        python3 \
        python3-pip \
        python3-dev \
        wget \
        tar \
        libcurl4 \
        openssl \
        openjdk-17-jre \
        iputils-ping \
        curl \
        proxychains4 && \
    \
    python3 -m pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    \
    rm -rf /tmp/*.tgz && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /root/.cache /var/lib/apt/lists/* && \
    cd /workspace &&\
    mkdir app/config #mount configuration folder here \
    mkdir app/log #mount logs here

WORKDIR /workspace/app/src
CMD ["python3", "-m", "main" ,"--config","../config/config.json","server"]
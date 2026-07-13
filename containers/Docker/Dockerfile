# API-only image intentionally avoids the DGL/GPU stack. This is enough for
# graph repository CRUD/read endpoints used by Thor. It is not enough for
# evaluation/metapath2vec/runtime graph recalculations; that path needs a
# separate GPU/DGL image or compose profile because the NVIDIA base image is
# multi-GB and hard to run portably in dev containers.
FROM python:3.10-slim AS builder

WORKDIR /workspace

COPY requirements-api.txt ./requirements-api.txt

RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        build-essential \
        python3-dev; \
    python3 -m venv /opt/graph-repo-venv; \
    /opt/graph-repo-venv/bin/python -m pip install --upgrade pip; \
    /opt/graph-repo-venv/bin/pip install --no-cache-dir -r requirements-api.txt; \
    rm -rf /root/.cache /var/lib/apt/lists/*

FROM python:3.10-slim AS runtime

LABEL author="Jozef Michal Bukas"
LABEL brief="Graph repository with system for domain evaluation based on the mutual relationships"

EXPOSE 8000

ENV PATH="/opt/graph-repo-venv/bin:${PATH}"

WORKDIR /workspace

COPY --from=builder /opt/graph-repo-venv /opt/graph-repo-venv
COPY src ./app/src
COPY containers/Docker/docker-entrypoint.sh /usr/local/bin/graph-repo-entrypoint
COPY containers/Docker/render_config_templates.py /usr/local/bin/render-config-templates

RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        libcurl4 \
        openssl \
        iputils-ping \
        curl \
        proxychains4; \
    apt-get autoremove -y; \
    apt-get clean; \
    rm -rf /var/lib/apt/lists/*; \
    mkdir -p app/config app/config-templates app/log; \
    chmod +x /usr/local/bin/graph-repo-entrypoint /usr/local/bin/render-config-templates

WORKDIR /workspace/app/src
ENTRYPOINT ["graph-repo-entrypoint"]
CMD ["python3", "-m", "main", "--config", "../config/config.json", "server"]

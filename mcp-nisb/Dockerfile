FROM python:3.11-slim-bookworm

WORKDIR /srv

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8

RUN set -eux; \
    rm -rf /var/lib/apt/lists/*; \
    apt-get clean; \
    apt-get -o Acquire::Retries=5 -o DPkg::Lock::Timeout=120 update; \
    apt-get -o Acquire::Retries=5 -o DPkg::Lock::Timeout=120 install -y --no-install-recommends \
        python3-dev \
        libxml2-dev \
        libxslt1-dev \
        libjpeg-dev \
        zlib1g-dev \
        gcc \
        g++ \
        fonts-noto-cjk \
        fonts-wqy-zenhei \
        fontconfig \
        pkg-config \
        libopenblas-dev \
        docker.io \
        libreoffice-core \
        libreoffice-common \
        libreoffice-writer \
        libreoffice-impress \
    ; \
    fc-cache -fv; \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt /srv/requirements.txt

RUN python -m pip install --upgrade pip setuptools wheel \
    && python -m pip install -r /srv/requirements.txt

COPY nisb_mcp.py /srv/nisb_mcp.py
COPY api_gateway.py /srv/api_gateway.py
COPY schema.json /srv/schema.json
COPY core/ /srv/core/
COPY tools/ /srv/tools/

RUN mkdir -p \
    /srv/integrations \
    /srv/tools/recall \
    /srv/tools/query \
    /srv/tools/save \
    /srv/tools/annotate \
    /srv/tools/corpus \
    /srv/tools/interpreter \
    /srv/tools/filesystem \
    /srv/tools/relations \
    /srv/tools/entities \
    /srv/tools/doc \
    && touch \
    /srv/core/__init__.py \
    /srv/tools/__init__.py \
    /srv/integrations/__init__.py \
    /srv/tools/recall/__init__.py \
    /srv/tools/query/__init__.py \
    /srv/tools/save/__init__.py \
    /srv/tools/annotate/__init__.py \
    /srv/tools/corpus/__init__.py \
    /srv/tools/interpreter/__init__.py \
    /srv/tools/filesystem/__init__.py \
    /srv/tools/relations/__init__.py \
    /srv/tools/entities/__init__.py \
    /srv/tools/doc/__init__.py

EXPOSE 8005 8006

CMD ["sh", "-c", "python3 /srv/nisb_mcp.py & uvicorn api_gateway:app --host 0.0.0.0 --port 8006 --app-dir /srv"]

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    git \
    bash \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 10001 gods

WORKDIR /workspace
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

USER gods
ENTRYPOINT ["/entrypoint.sh"]

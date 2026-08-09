# ---- Build stage ----
FROM python:3.12-slim AS builder

WORKDIR /app
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1

COPY requirements.txt .
RUN pip install --user -r requirements.txt

# ---- Runtime stage ----
FROM python:3.12-slim

WORKDIR /app
ENV PATH=/root/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY --from=builder /root/.local /root/.local
COPY . .

RUN chmod +x docker/entrypoint.sh

ENTRYPOINT ["docker/entrypoint.sh"]

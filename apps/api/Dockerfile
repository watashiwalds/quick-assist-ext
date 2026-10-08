# Một image cho cả API và worker — khác nhau ở lệnh chạy (xem infra/docker-compose*.yml)
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install . && useradd --system --uid 10001 --no-create-home app
COPY alembic.ini ./
COPY migrations ./migrations
COPY scripts ./scripts
# Không chạy bằng root (H02)
USER app
EXPOSE 8000
# --proxy-headers: lấy IP/scheme thật từ reverse proxy (Caddy) trong mạng nội bộ compose
CMD ["uvicorn", "quickassist.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]

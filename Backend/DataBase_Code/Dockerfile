# HuskyPoll backend only (API at SITE_URL/api), built from this folder:  docker build -t huskypoll-api .
# To ship the frontend in the same container, use deploy/Dockerfile.fullstack instead.
# One container, one process, SQLite + images on the /data volume.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    HUSKYPOLL_DB=/data/huskypoll.db \
    HUSKYPOLL_MEDIA_DIR=/data/media

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY huskypoll_db ./huskypoll_db
COPY huskypoll_api ./huskypoll_api
COPY migrations ./migrations
COPY alembic.ini ./

RUN useradd --create-home huskypoll && mkdir -p /data && chown huskypoll /data
USER huskypoll
VOLUME /data
EXPOSE 8000

# Apply any new migrations, then start ONE server process (SQLite has one writer;
# live updates are delivered in-process). --proxy-headers: trust X-Forwarded-* from
# the reverse proxy in front (nginx/Apache). The URL prefix comes from HUSKYPOLL_SITE_URL.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn huskypoll_api.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'"]

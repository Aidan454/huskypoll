FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HUSKYPOLL_DB=/data/huskypoll.db \
    HUSKYPOLL_MEDIA_DIR=/data/media

WORKDIR /app

# Install the project's existing dependencies before copying source files.
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY migrations/ ./migrations/
COPY alembic.ini pytest.ini ./
COPY tests/ ./tests/
COPY scripts/ ./scripts/
COPY samples/studentadmin-template.xlsx ./samples/studentadmin-template.xlsx

RUN useradd --create-home --uid 10001 huskypoll \
    && mkdir -p /data/media \
    && chown -R huskypoll:huskypoll /data
USER huskypoll

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

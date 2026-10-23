FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HUSKYPOLL_DB=/tmp/huskypoll.db

WORKDIR /app

# Install the project's existing dependencies before copying source files.
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY huskypoll_db/ ./huskypoll_db/
COPY migrations/ ./migrations/
COPY alembic.ini pytest.ini ./
COPY tests/ ./tests/
COPY scripts/ ./scripts/
COPY samples/studentadmin-template.xlsx ./samples/studentadmin-template.xlsx

RUN useradd --create-home --uid 10001 huskypoll
USER huskypoll

# No FastAPI application exists yet. Show the available database commands.
CMD ["python", "-m", "huskypoll_db", "--help"]

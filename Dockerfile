FROM python:3.11.9-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin appuser

COPY requirements.txt requirements.lock.txt ./
RUN pip install --no-cache-dir -r requirements.lock.txt

COPY src ./src
COPY config ./config
COPY contracts ./contracts
COPY scripts ./scripts

USER 10001:10001

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "src.service.app:app", "--host", "0.0.0.0", "--port", "8000"]

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

COPY services /app/services
COPY plugins /app/plugins

RUN mkdir -p /app/data

CMD ["python", "-m", "services.data_processor.main"]

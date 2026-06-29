FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN python -m pip install --upgrade "pip>=26.0,<27.0"
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ .

ENV PYTHONUNBUFFERED=1
ENV HF_HOME=/root/.cache/huggingface

CMD ["uvicorn", "web_app:app", "--host", "0.0.0.0", "--port", "8080"]

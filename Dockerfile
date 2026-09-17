FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV FASTEMBED_CACHE_PATH=/opt/fastembed_cache

ARG EMBEDDING_MODEL_NAME=BAAI/bge-small-en-v1.5

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

RUN python -c "from fastembed import TextEmbedding; TextEmbedding(model_name='${EMBEDDING_MODEL_NAME}', cache_dir='/opt/fastembed_cache')"

COPY app ./app
COPY tests ./tests
COPY evaluation ./evaluation

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY etl/requirements.txt etl/requirements.txt
RUN pip install --no-cache-dir -r etl/requirements.txt

COPY etl/src    etl/src
COPY etl/config etl/config
COPY sql/ddl    sql/ddl

# El Excel NO se copia a la imagen: se monta en /app/data/raw (ver docker-compose.yml)
RUN useradd --create-home etl && mkdir -p /app/docs/generados && chown -R etl /app
USER etl
WORKDIR /app/etl/src
CMD ["python", "-m", "etl.main"]

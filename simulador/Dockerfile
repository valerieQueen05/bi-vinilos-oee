FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
RUN pip install --no-cache-dir psycopg2-binary==2.9.10
COPY simulador.py forzar_falla.py receptor_alertas.py ./
RUN useradd --create-home sim && chown -R sim /app
USER sim
CMD ["python", "simulador.py"]

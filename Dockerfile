FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y libpq5 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code and Alembic files
COPY schema_propagation/ /app/schema_propagation/
COPY alembic.ini /app/alembic.ini
COPY alembic/ /app/alembic/

# Entrypoint
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENV PYTHONUNBUFFERED=1
ENTRYPOINT ["/entrypoint.sh"]

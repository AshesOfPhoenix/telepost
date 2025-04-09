FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including OpenSSL
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    ca-certificates \
    openssl \
    && rm -rf /var/lib/apt/lists/*

# Create certs directory and generate certificates
RUN mkdir -p certs && \
    openssl req -x509 -newkey rsa:4096 -nodes \
    -keyout certs/key.pem \
    -out certs/cert.pem \
    -days 365 \
    -subj "/CN=telepost-api.fly.dev"

# Copy requirements first for better caching
COPY ./api/requirements.txt ./requirements.txt
RUN pip install --upgrade pip
RUN pip install --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY .env .env
COPY ./api/ ./api

# Set environment variables
ENV PYTHONPATH=/app
ENV MODULE_NAME=api.main
ENV PORT=8080
ENV THREADS_SSL_CERT_FILEPATH=/app/certs/cert.pem
ENV THREADS_SSL_KEY_FILEPATH=/app/certs/key.pem

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080"]
# --------------------
# Base image
# --------------------
FROM python:3.11-slim

# --------------------
# Environment
# --------------------
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# --------------------
# Working directory
# --------------------
WORKDIR /app

# --------------------
# System dependencies
# --------------------
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# --------------------
# Python dependencies
# --------------------
RUN pip install --no-cache-dir \
    fastapi \
    uvicorn \
    sqlalchemy \
    pymysql \
    cryptography

# --------------------
# Create log directory (Linux standard)
# --------------------
RUN mkdir -p /var/log \
    && chmod 777 /var/log

# --------------------
# Copy application
# --------------------
COPY main.py /app/main.py

# --------------------
# Expose port
# --------------------
EXPOSE 8000

# --------------------
# Run application
# --------------------
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
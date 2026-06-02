# Backend container for Render (or any container host).
# The frontend deploys separately on Vercel — see DEPLOY.md.
FROM python:3.11-slim

# Faster, quieter Python; no .pyc clutter in the image.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/app/.cache/huggingface

WORKDIR /app

# Install the CPU-only PyTorch wheel first. The default PyPI torch bundles CUDA
# (~2GB) which blows past free-tier image limits; the CPU build is a fraction of
# the size and is all we need for local BGE embeddings.
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code (frontend and dev cruft are excluded via .dockerignore).
COPY app ./app
COPY scripts ./scripts
COPY schema.sql ./schema.sql

# Render injects $PORT; default to 8000 for local `docker run`.
ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

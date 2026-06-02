# Backend container.
# Runs on Hugging Face Spaces (Docker SDK — port 7860, container runs as UID
# 1000) and on any other container host (Render etc. inject their own $PORT).
# The frontend deploys separately on Vercel — see DEPLOY.md.
FROM python:3.11-slim

# Faster, quieter Python; no .pyc clutter in the image.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# HF Spaces run the container as UID 1000. Create a matching user with a
# writable HOME so the model cache (HF_HOME) and downloaded media land somewhere
# the runtime user can actually write.
RUN useradd -m -u 1000 user
ENV HOME=/home/user \
    HF_HOME=/home/user/.cache/huggingface \
    PORT=7860

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

# Hand the working dir to the runtime user so ingestion can write data/media.
RUN chown -R user:user /app
USER user

# HF expects 7860; other hosts override via $PORT.
EXPOSE 7860
CMD ["sh", "-c", "uvicorn app.api.main:app --host 0.0.0.0 --port ${PORT:-7860}"]

# -----------------------------
# Stage 1: Builder
# -----------------------------
FROM python:3.12-alpine AS builder

# Install build dependencies
RUN apk add --no-cache bash build-base libffi-dev openssl-dev ffmpeg curl wget

WORKDIR /app

# Copy requirements first for caching
COPY requirements.txt .

# Install Python dependencies to a temporary location
RUN pip install --upgrade pip \
    && pip install --no-cache-dir --prefix=/install -r requirements.txt

# Copy the app source code
COPY . /app

# -----------------------------
# Stage 2: Final Runtime
# -----------------------------
FROM python:3.12-alpine

WORKDIR /app

# Install runtime dependencies
RUN apk add --no-cache bash git ffmpeg curl wget

# Copy installed Python packages from builder
ENV PATH=/install/bin:$PATH
ENV PYTHONPATH=/install/lib/python3.12/site-packages:$PYTHONPATH
COPY --from=builder /install /install

# Copy application source code
COPY --from=builder /app /app

# Default command
CMD ["bash", "surf-tg.sh"]

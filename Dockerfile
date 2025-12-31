# ----------------------------------------------------------------------
# Stage 1: Build Stage (Only includes tools necessary for installation)
# ----------------------------------------------------------------------
FROM python:3.12-alpine AS builder

# Install build dependencies (for compiling C extensions like tgcrypto) and bash
RUN apk add --no-cache \
        bash \
        build-base \
        libffi-dev \
        openssl-dev \
        ffmpeg \
        curl \
        wget \
        && python -m ensurepip

# Set working directory
WORKDIR /app

# Copy requirements first to leverage caching
COPY requirements.txt .

# Upgrade pip and install Python dependencies
RUN pip install --upgrade pip \
    && pip install --prefix=/install --no-cache-dir -r requirements.txt

# Copy the rest of the source code
COPY . /app

# ----------------------------------------------------------------------
# Stage 2: Final Stage (Minimal Runtime Image)
# ----------------------------------------------------------------------
FROM python:3.12-alpine

# Set working directory
WORKDIR /app

# Install runtime dependencies
RUN apk add --no-cache \
        bash \
        git \
        ffmpeg \
        curl \
        wget

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Copy the application source code
COPY --from=builder /app /app

# Set default command
CMD ["bash", "surf-tg.sh"]

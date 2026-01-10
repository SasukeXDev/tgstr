# ----------------------------------------------------------------------
# Stage 1: Builder
# ----------------------------------------------------------------------
FROM python:3.12-alpine AS builder

# Install build dependencies for tgcrypto & cryptography
RUN apk add --no-cache \
    bash \
    build-base \
    libffi-dev \
    openssl-dev \
    cargo \
    ca-certificates

WORKDIR /app

# Copy requirements first for cache
COPY requirements.txt .

# Upgrade pip only (uv not required, avoids edge issues)
RUN pip install --upgrade pip

# Install python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy app source
COPY . /app


# ----------------------------------------------------------------------
# Stage 2: Runtime
# ----------------------------------------------------------------------
FROM python:3.12-alpine

WORKDIR /app

# Runtime dependencies (IMPORTANT)
RUN apk add --no-cache \
    bash \
    git \
    libstdc++ \
    libffi \
    openssl \
    ca-certificates

# Copy python site-packages
COPY --from=builder /usr/local/lib/python3.12/site-packages \
                    /usr/local/lib/python3.12/site-packages

# Copy app
COPY --from=builder /app /app

# 🔥 VERY IMPORTANT: clean old Pyrogram sessions at container start
RUN rm -f *.session *.session-journal || true

# Start
CMD ["bash", "surf-tg.sh"]

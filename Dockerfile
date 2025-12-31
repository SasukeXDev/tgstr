# ----------------------------------------------------------------------
# Stage 1: Build Stage (install Python deps only)
# ----------------------------------------------------------------------
FROM python:3.12-alpine AS builder

# Install build dependencies for Python C extensions
RUN apk add --no-cache \
        bash \
        build-base \
        libffi-dev \
        openssl-dev \
        ffmpeg \
        curl

# Set working directory
WORKDIR /app

# Copy requirements first for caching
COPY requirements.txt .

# Upgrade pip
RUN pip install --upgrade pip

# Install Python dependencies
RUN pip install --system --no-cache-dir -r requirements.txt

# Copy rest of the app
COPY . /app

# ----------------------------------------------------------------------
# Stage 2: Runtime Stage (minimal)
# ----------------------------------------------------------------------
FROM python:3.12-alpine

# Set working directory
WORKDIR /app

# Install runtime dependencies: bash + ffmpeg
RUN apk add --no-cache bash ffmpeg curl

# Copy Python dependencies from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages

# Copy app source
COPY --from=builder /app /app

# Create folder for HLS streams
RUN mkdir -p /app/streams/hls

# Expose Flask port
EXPOSE 5000

# Command to run when the container starts
CMD ["bash", "surf-tg.sh"]

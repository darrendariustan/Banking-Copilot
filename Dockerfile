# Use Python 3.11 for compatibility with PyTorch and dependencies
FROM python:3.11.9-slim

# Set working directory
WORKDIR /app

# Install system dependencies for audio processing and other requirements
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    portaudio19-dev \
    python3-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create cache directory
RUN mkdir -p cache

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

# Expose port (Render will set PORT env var dynamically)
# Note: EXPOSE requires a numeric value at build time, but Render will use the PORT env var at runtime
EXPOSE 8501

# Health check for Render (PORT is set by Render at runtime)
# Note: Health check is handled by Render's healthCheckPath, this is a fallback
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl --fail http://localhost:${PORT:-10000}/_stcore/health || exit 1

# Run the application (PORT will be set by Render)
CMD streamlit run app.py --server.port=${PORT:-8501} --server.address=0.0.0.0 --server.headless=true --server.fileWatcherType=none --browser.gatherUsageStats=false 
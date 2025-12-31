# ============================================================
# OryggiAI Gateway Agent - Docker Image
# ============================================================
# Simple Docker image for running the Gateway Agent
# No Python installation required on the host machine
# ============================================================

FROM python:3.11-slim

# Set labels
LABEL maintainer="OryggiAI <support@oryggi.ai>"
LABEL description="OryggiAI Gateway Agent - Secure database tunnel"
LABEL version="1.0.0"

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Install system dependencies for SQL Server ODBC
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gnupg2 \
    apt-transport-https \
    ca-certificates \
    unixodbc \
    unixodbc-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Microsoft ODBC Driver 18 for SQL Server (Debian 12 compatible)
RUN curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    && curl https://packages.microsoft.com/config/debian/12/prod.list | tee /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y msodbcsql18 \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY gateway_agent/ ./gateway_agent/

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash agent
RUN chown -R agent:agent /app
USER agent

# Default environment variables (override with docker-compose or -e flags)
ENV GATEWAY_TOKEN=""
ENV GATEWAY_SAAS_URL="wss://api.oryggi.ai/api/gateway/ws"
ENV DB_HOST="host.docker.internal"
ENV DB_PORT="1433"
ENV DB_DATABASE=""
ENV DB_USERNAME=""
ENV DB_PASSWORD=""
ENV DB_USE_WINDOWS_AUTH="false"
ENV DB_DRIVER="ODBC Driver 18 for SQL Server"
ENV LOG_LEVEL="INFO"

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Run the agent
CMD ["python", "-m", "gateway_agent"]

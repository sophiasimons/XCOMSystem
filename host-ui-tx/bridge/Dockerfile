FROM python:3.11-slim
# Set working directory
WORKDIR /usr/src/app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy and install requirements
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy Python files
COPY *.py ./
# Add healthcheck
HEALTHCHECK --interval=30s --timeout=3s \
    CMD curl -f http://localhost:8000 || exit 1
# Expose ports
EXPOSE 8000 8765
# Command to run the bridge application with proper host binding
CMD ["python", "./bridge.py", "--ws-port", "8765", "--web-port", "8000", "--host", "0.0.0.0"]

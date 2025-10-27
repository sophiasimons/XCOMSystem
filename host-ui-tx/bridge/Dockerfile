FROM python:3.11-slim
WORKDIR /app

# Copy and install requirements
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the bridge script
COPY bridge.py ./
COPY start.sh ./
RUN chmod +x start.sh

# Create directory for web files
RUN mkdir -p /app/web

# Expose both web UI and WebSocket ports
EXPOSE 8000 8765

# Use environment variable for bridge arguments
CMD sh -c 'python -m http.server 8000 --directory /app/web & python bridge.py $BRIDGE_ARGS'

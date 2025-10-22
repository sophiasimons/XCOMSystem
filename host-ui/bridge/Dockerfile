FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY bridge.py ./
EXPOSE 8765
CMD ["python", "bridge.py", "--ws-port", "8765"]

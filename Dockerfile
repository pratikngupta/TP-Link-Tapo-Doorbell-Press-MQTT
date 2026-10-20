FROM python:3.11-alpine

WORKDIR /app

# Ensure Python outputs are sent straight to terminal/docker logs without buffering
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY mqttsniffer.py .

CMD ["python", "mqttsniffer.py"]

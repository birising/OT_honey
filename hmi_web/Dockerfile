FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd -m -u 1000 appuser && \
    mkdir -p /data/logs && \
    chown -R appuser:appuser /app /data/logs

USER appuser

EXPOSE 80

CMD ["python", "app.py"]


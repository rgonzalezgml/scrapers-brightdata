FROM python:3.12-slim

WORKDIR /app

COPY requirements-prod.txt .
RUN pip install --no-cache-dir -r requirements-prod.txt

COPY . .

CMD ["python", "scheduler.py"]

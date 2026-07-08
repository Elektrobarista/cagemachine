FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1

# Dependencies zuerst (Layer-Caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 3000

# waitress (Produktionsserver); sh -c für FLASK_PORT-Expansion
CMD ["sh", "-c", "exec waitress-serve --host=0.0.0.0 --port=${FLASK_PORT:-3000} app:app"]

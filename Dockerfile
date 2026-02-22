FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Ensure directories exist
RUN mkdir -p uploads thumbnails

ENV BASE_URL=http://localhost:8000

EXPOSE 8000

CMD ["python", "-m", "flask", "--app", "app/main.py", "run", "--host=0.0.0.0", "--port=8000"]

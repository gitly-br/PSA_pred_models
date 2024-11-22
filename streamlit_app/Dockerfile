# Dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .

RUN apt-get update && \
    apt-get install -y libgdal-dev && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8501

ENV API_URL=http://psa_models_back:8000

ENTRYPOINT ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]

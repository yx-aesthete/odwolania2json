# Odwołania2json: CLI (input/ -> output/) i prototyp WWW. Bez GPU, model językowy tylko po API (LLM_BASE_URL).
FROM python:3.13-slim
RUN apt-get update \
 && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-pol \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt pyproject.toml run.sh ./
COPY src ./src
COPY config ./config
RUN pip install --no-cache-dir -r requirements.txt
ENV PYTHONPATH=/app/src PYTHONUNBUFFERED=1
ENTRYPOINT ["python", "-m", "odwolania2json"]
CMD ["--input", "/app/input", "--output", "/app/output"]

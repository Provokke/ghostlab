FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY ghostlab ./ghostlab
COPY web ./web
RUN pip install --no-cache-dir . fastapi uvicorn python-multipart httpx
ENV PORT=8080
CMD ["sh", "-c", "uvicorn ghostlab.server:app --host 0.0.0.0 --port ${PORT}"]

FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY ghostlab ./ghostlab
COPY web ./web
RUN pip install --no-cache-dir ".[web]"
RUN useradd -m app && mkdir -p /app/.cache && chown -R app /app
ENV PORT=8080 PYTHONUNBUFFERED=1 GHOSTLAB_CACHE=/app/.cache
USER app
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s CMD python -c "import os,urllib.request as u;u.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8080')+'/api/status',timeout=4)"
CMD ["sh", "-c", "uvicorn ghostlab.server:app --host 0.0.0.0 --port ${PORT}"]

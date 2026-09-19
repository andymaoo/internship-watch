FROM python:3.12.14-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt \
    && groupadd --gid 10001 internship-watch \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin internship-watch \
    && mkdir -p /app/data \
    && chown 10001:10001 /app/data
COPY internship_watch /app/internship_watch
COPY apple_scraper.py google_scraper.py meta_scraper.py seen.json /app/
USER 10001:10001
VOLUME ["/app/data"]
ENTRYPOINT ["python", "-m", "internship_watch"]
CMD ["--config", "/app/config.json", "daemon"]

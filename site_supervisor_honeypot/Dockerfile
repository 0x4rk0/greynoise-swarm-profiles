# Copeland Site Supervisor / E3 CXe honeypot
# Base: Debian Bookworm (python:3.11-slim-bookworm) — good Linux fingerprint match.
FROM python:3.11-slim-bookworm

ENV PORT=8010 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py plant_data.py log_history.py app_descriptions.py novel_vulns.py summary.html ./
COPY mirror ./mirror
COPY static ./static
COPY images ./images
COPY deploy ./deploy
COPY MANIFEST.md README.md ./

# Create empty logs dir in the image (do not COPY host logs/)
RUN mkdir -p /app/logs && chmod 777 /app/logs

RUN useradd -r -u 10001 -g nogroup sitesupervisor
USER sitesupervisor

EXPOSE 8010
CMD ["python", "server.py"]

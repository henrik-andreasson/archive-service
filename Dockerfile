FROM python:3.13-slim

# uid of the service user, match it to the owner of the bind-mounted data dir
ARG ARCHIVE_UID=1000

WORKDIR /archive-service

# Install dependencies first so they are cached between code changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ app/
COPY conf/defaultserviceconfig.py conf/
COPY archive-service.py gunicorn-start.sh ./

# /data is where archived files are stored, bind mount it from the host
RUN useradd -r -m -u "${ARCHIVE_UID}" archive \
 && mkdir -p /data /logs \
 && chown archive /archive-service /data /logs
USER archive

ENV PYTHONUNBUFFERED=1 \
    ARCHIVE_LOG_STDERR=true \
    ARCHIVE_UPLOAD_DIR=/data \
    ARCHIVE_LOG_DIR=/logs \
    PORT=8080 \
    FLASK_APP=/archive-service/archive-service.py

VOLUME ["/data", "/logs"]
EXPOSE 8080

CMD ["/archive-service/gunicorn-start.sh"]

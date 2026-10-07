# Docker

Archived files are stored in `/data` inside the container. Bind mount a host
directory there, otherwise the files are lost when the container is removed.
Logs are written to `/logs` and to `docker logs`.

The service runs as a non-root user with uid 1000. If the owner of your data
directory has another uid, build with `--build-arg ARCHIVE_UID=$(id -u)` (or set
`ARCHIVE_UID` for docker compose).

!!! warning "Create the directories first"
    If Docker creates the bind mounted directories they are owned by root and
    the service can't write to them, it then stops with a message saying how
    to fix the owner.

## docker compose

Stores files in `./archive-data` and logs in `./logs`:

```
mkdir -p archive-data logs
ARCHIVE_UID=$(id -u) docker compose up -d --build
```

`docker-compose.yml` passes these settings on from the environment:
`ARCHIVE_CLIENT_CERT`, `CERT`, `KEY`, `CA`, `ARCHIVE_PROXY_COUNT`,
`ARCHIVE_ALLOW_REMOVE`, `ARCHIVE_BUCKETS`, `ARCHIVE_TZ`, `ARCHIVE_DEBUG` and
`ARCHIVE_MAX_UPLOAD_MB`, eg.

```
ARCHIVE_ALLOW_REMOVE=true docker compose up -d
```

## docker run

Build the image:

```
docker build -t archive-service --build-arg ARCHIVE_UID=$(id -u) .
```

Run it:

```
mkdir -p archive-data logs
docker run -it -p 8080:8080 \
  --mount type=bind,source="$(pwd)/archive-data",target=/data \
  --mount type=bind,source="$(pwd)/logs",target=/logs \
  archive-service
```

## Settings

Set service settings as environment variables (`-e ARCHIVE_BUCKETS=cert,logs`),
all settings are listed in [Configuration](configuration.md). To use a config
file instead, mount it and point `ARCHIVE_CONFIG` at it:

```
docker run ... \
  --mount type=bind,source="$(pwd)/my-config.py",target=/config.py,readonly \
  -e ARCHIVE_CONFIG=/config.py archive-service
```

For TLS and client certificates see [TLS](tls.md).

## Health check from the host

Requests from the Docker host come from the Docker gateway address, eg.
`172.17.0.1`, not `127.0.0.1`. To call the health check from the host, add the
gateway to the allowed ips:

```
docker run ... -e ARCHIVE_IPS_HEALTH=127.0.0.1,172.17.0.1 archive-service
```

## Developer mode

Mount the source into the container and let Flask reload when a Python file
changes:

```
docker run -it -p 8080:8080 \
  --mount type=bind,source="$(pwd)",target=/archive-service \
  --mount type=bind,source="$(pwd)/archive-data",target=/data \
  archive-service flask run --host=0.0.0.0 --port=8080 --reload
```

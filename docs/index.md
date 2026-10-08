# Archive Service

Inspired by S3, but with the focus on a simple way to upload files to an
archive, so they can be deleted locally.

* upload a file with an HTTP POST or the [client](client.md), the server
  returns a uuid and the sha256 of the stored file
* the client compares the sha256 with its own, and can delete the local file
  once it is safely archived
* TLS with client certificates, see [TLS](tls.md)
* runs in Docker, see [Docker](docker.md), or directly with gunicorn, see
  [Run the server](run-server.md)

## How files are stored

Each client gets its own part of the archive, based on its ip address. When a
file is stored the client chooses a **bucket**, the server adds a directory
with the **date** and stores the file under a new **uuid**:

```
<ARCHIVE_UPLOAD_DIR>/<client ip>/<bucket>/<date>/<uuid>
```

eg.

```
/data/10.1.2.3/backups/2026-10-06/f71f4bd0-22de-474e-8554-81f381e766ed
```

* **bucket** - one of the allowed buckets, default
  `cert, other, log, config, admin, backups` (`ARCHIVE_BUCKETS`)
* **date** - the day the file was stored, `YYYY-MM-DD` in the time zone
  `ARCHIVE_TZ` (default `Europe/Stockholm`)
* **uuid** - returned when the file is stored, together with the bucket and
  date it is needed to get, hash or delete the file

Next to each file the server keeps `<uuid>.json` with the original file name,
size, sha256 and the time it was stored. `list` with `?details=1` returns this
for the files on a date, see [API](api-doc.md).

A client can only see and get its own files. Deleting files is off by default
(`ARCHIVE_ALLOW_REMOVE`). See [Configuration](configuration.md) for all
settings.

## Quick start

Start the server with docker compose, the files are stored in
`./archive-data`:

```
mkdir -p archive-data logs
ARCHIVE_UID=$(id -u) docker compose up -d --build
```

Store a file and get it back with the client:

```
pip install -r requirements-cli.txt
export ARCHIVE_URL=http://localhost:8080

bin/archive-cli.py store README.md -b cert
# file archived OK;file:README.md;uuid:<uuid>;bucket:cert;date:<date>;hash:<sha256>

bin/archive-cli.py get <uuid> -b cert -t <date> -o README-back.md
```

This runs plain HTTP, for production use TLS with client certificates, see
[TLS](tls.md).

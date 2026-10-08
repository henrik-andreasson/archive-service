Archive Service
================

Inspired by S3, but with the focus on a simple way to upload files to an
archive, so they can be deleted locally.

* store a file and get back a uuid and the sha256 of the stored file, the
  client checks the hash and can delete the local copy
* each client (ip address) has its own part of the archive, files are stored
  as `<client ip>/<bucket>/<date>/<uuid>`
* TLS with client certificates, runs in Docker or directly with gunicorn
* the client can store on several servers, clustered or standalone
* an optional web UI to upload and browse files

# Quick start

Start the server with docker compose, files are stored in `./archive-data`:

```
mkdir -p archive-data logs
ARCHIVE_UID=$(id -u) docker compose up -d --build
```

Or without Docker:

```
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
mkdir -p archive-data logs
export ARCHIVE_UPLOAD_DIR="$PWD/archive-data"
export ARCHIVE_LOG_DIR="$PWD/logs"
./gunicorn-start.sh
```

Store a file and get it back with the client:

```
pip install -r requirements-cli.txt
export ARCHIVE_URL=http://localhost:8080

bin/archive-cli.py store README.md -b cert
bin/archive-cli.py get <uuid> -b cert -t <date> -o README-back.md
```

This runs plain HTTP, for production use TLS with client certificates.

# Docs

* [Overview](docs/index.md) - how files are stored
* [Run the server](docs/run-server.md) and [Docker](docs/docker.md)
* [Configuration](docs/configuration.md) - all settings
* [TLS and client certificates](docs/tls.md)
* [Client](docs/client.md)
* [Web UI](docs/web-ui.md) - upload and browse in the browser (off by default)
* [API](docs/api-doc.md)
* [Development](docs/development.md) - tests and building these docs

The docs can also be built as a website with Material for MkDocs, see
[Development](docs/development.md#documentation).

# Tests

```
./run-tests.sh                        # all tests, creates .venv on the first run
./run-tests.sh -m "not integration"   # only the fast tests, no real servers
```

The tests also run on GitHub Actions on every push (`.github/workflows/tests.yml`).

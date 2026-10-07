# Run the server

The server is a Flask app run by gunicorn. The easiest way to run it is
[Docker](docker.md), this page describes running it directly.

Needs Python 3.11 or newer.

## Install

```
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Start

`gunicorn-start.sh` starts gunicorn on port 8080, with TLS if `CERT` and `KEY`
are set (see [TLS](tls.md)). Put the virtualenv on the `PATH`:

```
mkdir -p archive-data logs

export PATH="$PWD/.venv/bin:$PATH"
export ARCHIVE_UPLOAD_DIR="$PWD/archive-data"
export ARCHIVE_LOG_DIR="$PWD/logs"

./gunicorn-start.sh
```

Check that it answers:

```
curl http://localhost:8080/
```

`gunicorn-start.sh` writes `archive.pid` into the service directory (it is
in `.gitignore`). In TLS mode the cert files are written to a private
directory in `/dev/shm`, which is in memory, see [TLS](tls.md).

### Start script settings

| Variable | Default | Description |
|---|---|---|
| `INSTALL_PATH` | the directory of `gunicorn-start.sh` | directory of the service |
| `PORT` | `8080` | port to listen on |
| `TIMEOUT` | `300` | gunicorn worker timeout in seconds, large uploads on slow connections need time |
| `CERT`, `KEY` | - | server cert and key (PEM), both enable TLS |
| `CA` | - | CA cert used to verify client certificates |
| `ARCHIVE_CLIENT_CERT` | `on` when TLS is enabled | `on`/`off`, require client certificates |
| `TLS_DIR` | a new private dir in `/dev/shm` (or `/tmp`) | where the cert files are written |
| `OPTIONS` | - | extra gunicorn options, eg. `--workers 4` |

All settings are checked before anything is written, bad values stop the
script with an error.

The service settings (`ARCHIVE_*`) are described in
[Configuration](configuration.md).

!!! note "Large uploads"
    gunicorn stops a worker that is busy for longer than `TIMEOUT` (300
    seconds), raise it if large uploads over slow connections are cut off.

## Development server

For development, Flask's own server reloads when the code changes:

```
FLASK_APP=archive-service.py ARCHIVE_UPLOAD_DIR=$PWD/archive-data ARCHIVE_LOG_DIR=$PWD/logs \
  .venv/bin/flask run --debug --port 8080
```

Don't use it in production.

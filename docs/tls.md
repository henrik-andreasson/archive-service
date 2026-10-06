# TLS and client certificates

TLS is terminated in gunicorn. It is enabled by giving `gunicorn-start.sh` the
server certificate and key, and with a CA the server also requires client
certificates.

| Variable | Description |
|---|---|
| `CERT`, `KEY` | server cert and key (PEM), both are needed to enable TLS |
| `CA` | CA cert (PEM) used to verify client certificates |
| `ARCHIVE_CLIENT_CERT` | `on`/`off`, require client certificates, default `on` when TLS is enabled |

The PEM values are the file contents, newlines may be replaced with `;`, which
is easier to pass as an environment variable:

```
CERT="$(tr '\n' ';' < server.crt)"
```

`gunicorn-start.sh` checks all settings first, then writes the files to a new
private directory (mode 700, files 600) in `/dev/shm`, which is in memory, so
the private key is not stored on disk or in the container's writable layer.
Set `TLS_DIR` to use another directory.

## What happens

| Settings | Result |
|---|---|
| `CERT` + `KEY` + `CA` | TLS, client certificates required and verified against `CA` |
| `CERT` + `KEY` + `ARCHIVE_CLIENT_CERT=off` | TLS only, any client may connect (eg. automated tests), a warning is printed |
| `CERT` + `KEY`, no `CA` | refuses to start, set `CA` or `ARCHIVE_CLIENT_CERT=off` |
| only `CERT` or only `KEY` | refuses to start |
| no TLS | plain HTTP, a warning is printed |
| no TLS + `ARCHIVE_CLIENT_CERT=on` | refuses to start |

## Docker

```
docker run -it -p 8080:8080 \
  -e CERT="$(tr '\n' ';' < server.crt)" \
  -e KEY="$(tr '\n' ';' < server.key)" \
  -e CA="$(tr '\n' ';' < ca.crt)" \
  --mount type=bind,source="$(pwd)/archive-data",target=/data \
  archive-service
```

`docker-compose.yml` passes `CERT`, `KEY`, `CA` and `ARCHIVE_CLIENT_CERT` on
from the environment.

## Client

```
export ARCHIVE_URL=https://archive.example.com:8080
export ARCHIVE_CERT=client.crt
export ARCHIVE_KEY=client.key
export ARCHIVE_CA=ca.crt          # CA of the server cert, default the system CAs

bin/archive-cli.py health
```

The server name in `ARCHIVE_URL` must match the server certificate.

## Test certificates

`conf/test-certs/` has certificates for testing, **don't use them in
production**:

| File | |
|---|---|
| `ca.pem` | test CA (Gazonk CA) |
| `archive-server.test.gazonk.se.{crt,key}` | server cert for `archive-server.test.gazonk.se` |
| `archive-client.test.gazonk.se.{crt,key}` | client cert |

The server cert is only valid for `archive-server.test.gazonk.se`, add it to
`/etc/hosts` or use `curl --resolve`:

```
curl --resolve archive-server.test.gazonk.se:8080:127.0.0.1 \
  --cacert conf/test-certs/ca.pem \
  --cert conf/test-certs/archive-client.test.gazonk.se.crt \
  --key conf/test-certs/archive-client.test.gazonk.se.key \
  https://archive-server.test.gazonk.se:8080/
```

!!! note "Making your own CA"
    Python 3.13 rejects CA certificates without a key usage extension, a CA
    needs `basicConstraints=critical,CA:TRUE` and
    `keyUsage=critical,keyCertSign,cRLSign`.

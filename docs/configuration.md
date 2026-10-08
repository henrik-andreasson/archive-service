# Configuration

All settings are environment variables with defaults in
`conf/defaultserviceconfig.py`. They can also be put in an optional Python
file, see `conf/archive-service-config.py.example`.

Order: built in defaults → environment variables → config file (the file wins).

The settings are printed at startup (on stderr), values of settings with
`SECRET`, `PASSWORD` or `TOKEN` in the name are hidden. Bad values, eg. an
unknown time zone or a number that is not a number, stop the service at
startup with an error.

## Service settings

| Variable | Default | Description |
|---|---|---|
| `ARCHIVE_CONFIG` | `conf/archive-service-config.py` | optional config file, if set the file must exist |
| `ARCHIVE_UPLOAD_DIR` | `/tmp` (`/data` in docker) | where archived files are stored |
| `ARCHIVE_BUCKETS` | `cert,other,log,config,admin,backups` | allowed buckets |
| `ARCHIVE_ALLOW_REMOVE` | `false` | allow clients to delete files (HTTP DELETE) |
| `ARCHIVE_IPS_HEALTH` | `127.0.0.1,127.0.0.2` | ips allowed to call the health check |
| `ARCHIVE_TZ` | `Europe/Stockholm` | time zone for the date dirs and health timestamps |
| `ARCHIVE_PROXY_COUNT` | `0` | number of trusted reverse proxies, see [below](#client-address-and-reverse-proxies) |
| `ARCHIVE_UI` | `false` | serve the web front-end at `/ui/` |
| `ARCHIVE_MAX_UPLOAD_MB` | `1024` | largest upload in MB, larger uploads get 413, `0` = no limit |
| `ARCHIVE_LOG_DIR` | `/tmp` (`/logs` in docker) | log directory |
| `ARCHIVE_LOG_FILE` | `archive-service.log` | log file name, empty = no log file (the old name `ARCHIVE_LOGFILE` also works) |
| `ARCHIVE_LOG_MAX_MB` | `10` | rotate the log file at this size, `0` = never |
| `ARCHIVE_LOG_BACKUPS` | `10` | number of rotated log files to keep |
| `ARCHIVE_LOG_STDERR` | `false` (`true` in docker) | also log to stderr, eg. for `docker logs` |
| `ARCHIVE_DEBUG` | `false` | debug logging |

* **lists** (`ARCHIVE_BUCKETS`, `ARCHIVE_IPS_HEALTH`) are comma separated,
  eg. `ARCHIVE_BUCKETS="cert,other,log"`. Bucket names and ip addresses must
  match an entry exactly.
* **booleans** accept `true/false`, `yes/no`, `on/off` and `1/0`.

The start script `gunicorn-start.sh` has its own settings (port, TLS), see
[Run the server](run-server.md#start-script-settings). The Docker build arg
`ARCHIVE_UID` is described in [Docker](docker.md).

## Config file

Copy `conf/archive-service-config.py.example` to
`conf/archive-service-config.py`, or point `ARCHIVE_CONFIG` at your own file.
It is Python, so lists and booleans can be written as such:

```python
ARCHIVE_BUCKETS = ["cert", "backups"]
ARCHIVE_ALLOW_REMOVE = True
```

## Client address and reverse proxies

Each client gets its own part of the archive, based on its ip address.

By default (`ARCHIVE_PROXY_COUNT=0`) the address of the TCP connection is used
and the `X-Forwarded-For` header is ignored. This is the right setting when
clients connect directly to the service, eg. TLS terminated in gunicorn.

If the service runs behind reverse proxies, set `ARCHIVE_PROXY_COUNT` to the
number of proxies. The client address is then taken from `X-Forwarded-For`,
only the entries added by the trusted proxies are used. Never set it when
clients can connect directly, they could then pretend to be any address.

Addresses that are not valid ip addresses are rejected, as are dates not
formatted `YYYY-MM-DD` and file names that are not a uuid.

!!! note "Docker"
    Connections from the Docker host itself, and with rootless Docker, go
    through Docker's proxy and all get the gateway address (eg. `172.17.0.1`).
    Remote clients keep their own address. Use `network_mode: host` if all
    clients must be told apart.

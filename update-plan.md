# Archive Service – Update Plan

Review of the repo with suggested improvements to dependencies (requirements.txt), Docker, security, config, client and packaging.

Order of work:

1. ~~Requirements (§1), Docker (§2)~~ ✅ done.
2. ~~Security (§3), config (§4), client (§5)~~ ✅ done.
3. ~~Server code quality (§6), packaging (§7)~~ ✅ done.
4. ~~Automated test suite (§8)~~ ✅ done.
5. ~~Documentation (§9)~~ ✅ done.
6. ~~Fixes (§10)~~ ✅ done.

The security items change behaviour (delete off by default, `X-Forwarded-For` ignored unless a proxy is configured). Check that this is acceptable for current deployments.

---

## 1. Requirements: what the code actually uses ✅ DONE

**Status:** Fixed.

- Added `requirements.txt` and `requirements-cli.txt` with the contents below.
- Removed the `flask_bootstrap` import and `Bootstrap()` setup from `app/__init__.py`.
- Tested: in a fresh virtual environment the app started, `/` and `/archive/health/v1/` returned 200, and `archive-cli.py --help` ran.
- The `Dockerfile` now installs from `requirements.txt` (done in §2).
- Added `werkzeug>=3.0,<4` and `click>=8.1` to `requirements.txt`. The code imports them directly (`ProxyFix` from §3.2, `secure_filename`, `app/cli.py`), so they're listed explicitly rather than relying on Flask pulling them in.

Original findings:

Before this fix there was no `requirements.txt`; dependencies were installed inline in the `Dockerfile`.

| Package | Used? | Notes |
|---|---|---|
| `flask` | yes | Not in the Dockerfile; only installed because other packages depend on it. |
| `gunicorn` | yes | Used by `gunicorn-start.sh`. |
| `flask-bootstrap` | barely | `app/__init__.py` sets it up, but there are no templates. Drop it and remove the import. |
| `flask-login` | **no** | Remove. |
| `flask-httpauth` | **no** | Remove. |
| `sqlite` (OS package) | **no** | Remove. |
| `requests` | client only | Used by `bin/archive-cli.py`. |

Suggested files:

```
# requirements.txt  (server)
flask>=3.0,<4
gunicorn>=22
```

```
# requirements-cli.txt  (client)
requests>=2.32
```

## 2. Dockerfile ✅ DONE

**Status:** Fixed.

- `Dockerfile` rewritten:
  - Based on `python:3.13-slim`; installs from `requirements.txt`.
  - Copies only `app/`, `conf/defaultserviceconfig.py`, `archive-service.py` and `gunicorn-start.sh`.
  - Runs as the non-root user `archive` with a home dir. The uid is set by build arg `ARCHIVE_UID` (default 1000) so it can match the owner of the host data dir.
  - Sets `ARCHIVE_UPLOAD_DIR=/data` and `ARCHIVE_LOG_DIR=/logs`, declares both as volumes, and exposes port 8080.
- Added `.dockerignore`: excludes `.git`, test certs/keys, the local config file, `docs/`, `bin/` and local data/log dirs.
- **Bind mount for stored files:** a Dockerfile can't create bind mounts; they're set at run time.
  - Added `docker-compose.yml`, which bind-mounts `./archive-data` → `/data` and `./logs` → `/logs`. Create the host dirs first (`mkdir -p archive-data logs`); if Docker creates them they are owned by root and the service fails to start. `gunicorn-start.sh` checks that `/data` and `/logs` are writable and exits with a clear message saying how to fix ownership.
  - `docs/docker.md` documents compose, the matching `docker run --mount` commands and the uid setting.
  - `archive-data/` added to `.gitignore`.
- Tested: the image builds. With `/data` bind-mounted, a `store` call returned 200, the file appeared on the host under `<ip>/cert/<date>/<uuid>`, and the container logs had no errors.
- Note: TLS mode in `gunicorn-start.sh` writes cert files and the pid file into `/archive-service`, inside the container layer. Moved to §10.

Original findings:

- `FROM alpine` + `RUN yum install` will fail because Alpine uses `apk`. Even with `apk`, a plain `pip3 install` fails on recent Alpine because the system Python blocks it (PEP 668).
- `EXPOSE 5002`, but `gunicorn-start.sh` defaults to 8080 and `docs/docker.md` uses 8080.
- It copies the whole repo, including test keys and `.git`. There's no `.dockerignore`.
- It runs as root.

Suggested replacement:

```dockerfile
FROM python:3.13-slim
WORKDIR /archive-service
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app conf archive-service.py gunicorn-start.sh ./
RUN useradd -r archive && mkdir -p /data /logs && chown archive /data /logs
USER archive
ENV ARCHIVE_UPLOAD_DIR=/data ARCHIVE_LOG_DIR=/logs PORT=8080
VOLUME ["/data", "/logs"]
EXPOSE 8080
CMD ["./gunicorn-start.sh"]
```

## 3. Security problems (fix before improving usability) ✅ DONE

1. ✅ **DONE – Client certificates are never checked.** `gunicorn-start.sh` writes `ca.pem` but never passes `--ca-certs` / `--cert-reqs 2` to gunicorn, so the TLS setup in the docs does nothing. Anyone can use the API.

   **Status:** Fixed in `gunicorn-start.sh`, with client certificates as an on/off option.
   - New env var `ARCHIVE_CLIENT_CERT=on|off`. Unset means on when TLS is enabled.
   - TLS (`CERT` + `KEY`) + `CA` → gunicorn runs with `--ca-certs ca.pem --cert-reqs 2`, so client certs are required and verified.
   - TLS + `ARCHIVE_CLIENT_CERT=off` → TLS only, with a warning. Intended for automated tests.
   - TLS without `CA` and not `off` → refuses to start instead of silently running without client auth.
   - No TLS → plain HTTP with a warning; `ARCHIVE_CLIENT_CERT=on` without TLS refuses to start.
   - Invalid value, or only one of `CERT`/`KEY` set → refuses to start. (Previously any two of CERT/CA/KEY enabled TLS.)
   - `key.pem` is now `chmod 600`, gunicorn is started with `exec` so it receives signals, and the pid file is always written.
   - `docker-compose.yml` passes `ARCHIVE_CLIENT_CERT`, `CERT`, `KEY` and `CA` through; `docs/docker.md` documents them.
   - Tested in Docker with freshly generated certs:
     - Required mode: no client cert → rejected; cert from another CA → rejected; valid client cert → 200.
     - `off` → 200 without a client cert.
     - Plain HTTP → 200.
     - All misconfigurations exit 1 with a clear error.
   - Follow-ups (all done):
     - ✅ New test certs issued in `conf/test-certs/`:
       - `ca.pem` (Gazonk CA, valid to 2036).
       - `archive-server.test.gazonk.se.{crt,key}` and `archive-client.test.gazonk.se.{crt,key}`, valid to Oct 2027 with correct key usage / EKU.
       - Verified: chain OK, keys match. End to end in Docker, no client cert and the old demo cert were rejected; the new client cert got 200 and a `store` worked.
       - The server cert's SAN is `archive-server.test.gazonk.se`, so clients must use that hostname (e.g. via `/etc/hosts` or `curl --resolve`).
     - ✅ Removed the expired demo files (`archive-*-demo.*`, `archive-demo.ca`) and rewrote `conf/test-certs/readme.txt` for the new certs.
     - ✅ Client cert is optional in the client, matching `off` mode (done in §5).
2. ✅ **DONE – `X-Forwarded-For` is trusted without checks and used as a filesystem path.**

   **Status:** Fixed. TLS ends in gunicorn inside the container, so there is normally no proxy.
   - `X-Forwarded-For` is now ignored by default; the client address is the TCP peer (`request.remote_addr`).
   - Optional proxy support: `ARCHIVE_PROXY_COUNT` (default 0). When > 0, Werkzeug's `ProxyFix(x_for=N)` is enabled and only the entries added by the trusted proxies are used. The old code used the leftmost entry, which the client controls.
   - New helper `get_remote_addr()` validates the address with `ipaddress.ip_address()`. Anything else returns 400 "Invalid client address".
   - New helper `check_path_args()`: `date` must match `YYYY-MM-DD` and `filename` must be a uuid. Applied in get, hash, delete and list; returns 400.
   - `list` now checks the bucket against `ARCHIVE_BUCKETS`. Before, `/archive/list/v1/../` listed every client's folder.
   - Documented in `docs/config-server.md`; `docker-compose.yml` passes `ARCHIVE_PROXY_COUNT` through.
   - Tested with Flask's test client:
     - Spoofed XFF ignored for get, list (`/etc`) and health (`127.0.0.1`).
     - Another client's IP can't read the file.
     - `..` as bucket, date or filename → 403/400.
     - Normal store, get, hash and list → 200.
     - With `ARCHIVE_PROXY_COUNT=1`: the proxy-supplied address is used, the rightmost entry wins, and XFF `/etc` → 400.
   - Docker caveat: connections from the Docker host, rootless Docker and some IPv6 setups go through docker-proxy and all appear as the gateway IP. Use `network_mode: host` if that matters.
   - Possible later improvement: key folders by client cert CN instead of IP (needs the peer cert from the gunicorn socket).

   Original finding:
   - Any client can set it to another IP and read or delete that client's files.
   - It also bypasses `ARCHIVE_IPS_HEALTH`.
   - Worse, `os.path.join(UPLOAD_DIR, "/etc")` resolves to `/etc`. So `GET /archive/list/v1/` with `X-Forwarded-For: /etc` lists any directory on the server, and `store` can write under any path.
   - Fix: only honour the header behind a known proxy (Werkzeug's `ProxyFix`), check the value with `ipaddress.ip_address()`, and validate `date` against `^\d{4}-\d{2}-\d{2}$`.
3. ✅ **DONE – Delete is on by default, and the off switch doesn't work.**

   **Status:** Fixed.
   - `ARCHIVE_ALLOW_REMOVE` is parsed with the new `to_bool()` in `conf/defaultserviceconfig.py` (`1/true/yes/on`, any case) and defaults to **false**. The delete handler checks `to_bool(...)` instead of `== 0`.
   - The delete route only accepts HTTP `DELETE`; GET returns 405. The client uses `requests.delete` (now `archive-cli.py delete`, §5).
   - `docs/api-doc.md` and `docs/config-server.md` are updated; `docker-compose.yml` passes `ARCHIVE_ALLOW_REMOVE` through (default false).
   - Tested with Flask's test client:
     - unset, `0`, `false`, `no` → GET 405, DELETE 403.
     - `1`, `true`, `TRUE`, `on` → GET 405, DELETE 200.
   - Breaking change: scripts calling delete with GET must use `-X DELETE`, and deletes need `ARCHIVE_ALLOW_REMOVE=true`.
   - `to_bool()` is reused for the other settings (§4).
   - ✅ A missing file now returns 404 instead of 403 (fixed in §6).

   Original finding:
   - The default is `ARCHIVE_ALLOW_REMOVE = 1`, but the docstring says "default off".
   - Environment variables are strings and the check is `== 0`, so `ARCHIVE_ALLOW_REMOVE=0` still allows deletes.
   - Delete also runs on a GET request.
4. ✅ **DONE – Bucket check does substring matching when set from the environment.**

   **Status:** Fixed.
   - New `to_list()` in `conf/defaultserviceconfig.py` turns comma-separated strings (also the quoted `'"cert","other"'` form) into lists, trimming spaces and quotes and dropping empty entries.
   - Used for `ARCHIVE_BUCKETS` and `ARCHIVE_IPS_HEALTH` in `Config`, and again in `create_app()` after the optional config file loads. All existing `in` checks are now exact matches without touching the handlers.
   - Documented in `docs/config-server.md`.
   - Tested with `ARCHIVE_BUCKETS="cert,other"` and `ARCHIVE_IPS_HEALTH="127.0.0.1"`:
     - store to `cert`/`other` → 200; `ce`, `r`, `t,o` → 403 (was 200).
     - health from `127.0.0.1` → 200; `27.0.0.1`, `7.0.0.1` → 403 (was 200).

   Original finding: `ARCHIVE_BUCKETS` arrives as a string, so `"ce" in "cert,other"` is True. The same applies to `ARCHIVE_IPS_HEALTH`.
5. ✅ **DONE – Config, including the secret key, is printed to stdout**
   - **Status:** Fixed in `create_app()`:
     - Startup now prints only `ARCHIVE_*` settings, sorted, so Flask internals are no longer dumped.
     - Any key containing `SECRET`, `PASSWORD` or `TOKEN` is shown as `***`, or `(not set)` if empty.
     - Tested with `ARCHIVE_SECRET_KEY=topsecret123`: the output shows `ARCHIVE_SECRET_KEY = ***` and the value appears nowhere.
   - ✅ `ARCHIVE_SECRET_KEY` was unused and has been removed (§4).

   Original finding: config, including the secret key, is printed to stdout at startup (`app/__init__.py:17-18`).

## 4. Config bugs (the main ease-of-use problem) ✅ DONE

**Status:** Fixed.

- **Parsing in one place:** `normalize_config()` in `conf/defaultserviceconfig.py` runs in `create_app()` after the defaults, environment and config file are loaded.
  - Lists use `to_list` (`ARCHIVE_BUCKETS`, `ARCHIVE_IPS_HEALTH`).
  - Booleans use `to_bool` (`ARCHIVE_ALLOW_REMOVE`, `ARCHIVE_DEBUG`).
  - `ARCHIVE_PROXY_COUNT` must be an int ≥ 0, and `ARCHIVE_TZ` is checked as a real time zone.
  - Bad values stop startup with a readable error. `Config` now only holds the raw defaults and environment values.
- **Config file loading fixed:** it's loaded from `ARCHIVE_CONFIG` (default `conf/archive-service-config.py`, resolved from the `conf/` dir; `instance_relative_config` removed). If `ARCHIVE_CONFIG` is set and the file is missing, startup fails. Order: defaults → environment → file.
- **Sample config renamed** to `conf/archive-service-config.py.example`, with correct Python values, all commented out. Otherwise its test values (buckets `foo,bar`, delete on, debug on) would start applying now that loading works. `conf/archive-service-config.py` is added to `.gitignore`.
- **`ARCHIVE_DEBUG` works:** `log.py` reads it instead of Flask's `DEBUG`. Also fixed removing log handlers while iterating over the same list.
- **Log file name:** `ARCHIVE_LOG_FILE` is now read from the environment; the old `ARCHIVE_LOGFILE` still works as a fallback.
- **`ARCHIVE_TZ` is used** for the date folders and the health timestamp (new `now()` helper in `archive.py`). Previously the server's local time was used, which is UTC in the container.
- **`ARCHIVE_SECRET_KEY` removed:** nothing used it.
- **Docs:** the README has a configuration table covering service settings, `gunicorn-start.sh` variables and the Docker build arg. `docs/config-server.md` points to it. `docs/docker.md` shows mounting a config file. `docker-compose.yml` passes `ARCHIVE_BUCKETS`, `ARCHIVE_TZ` and `ARCHIVE_DEBUG` through.
- **Docker:** `PYTHONUNBUFFERED=1` added, so startup/config output appears in `docker logs` immediately. Before, it only showed when the process exited.
- **Tested:**
  - Defaults and environment parsing (`"cert, other"`, `YES`, `on`, `2`) give the right types.
  - Debug mode sets log level DEBUG and writes debug lines.
  - Old and new log-file names work; the new one wins.
  - A config file overrides the environment, including string values.
  - A missing `ARCHIVE_CONFIG` file, unknown TZ, non-numeric or negative proxy count each stop startup with a clear error.
  - Store's date folder follows `ARCHIVE_TZ`: `Pacific/Kiritimati` gave 2026-10-07 while UTC was 2026-10-06, and delete still works.
  - The Docker image builds, starts and prints the config.
- Behaviour change: date folders are now in `Europe/Stockholm` time by default instead of the container's UTC. Files stored around midnight may land in a different date folder than before; existing files are unaffected.

Original findings:

- `conf/archive-service-config.py` is **never loaded**. With `instance_relative_config=True`, Flask looks for it under `instance/conf/`. Its values are also in the wrong format (`'"foo","bar"'` is a string, not a list).
- `ARCHIVE_DEBUG` is never read; `log.py` checks Flask's own `DEBUG`.
- The setting is called `ARCHIVE_LOG_FILE`, but it reads the environment variable `ARCHIVE_LOGFILE`.
- `ARCHIVE_SECRET_KEY` and `ARCHIVE_TZ` are unused.

Suggested fix: one small parser that turns comma-separated values into lists and `true/1/yes` into booleans, defaulting to `ALLOW_REMOVE=false`. Load an optional file from an `ARCHIVE_CONFIG` path variable. Document every variable in one table in the README.

## 5. Client bugs (`bin/archive-cli.py`) ✅ DONE

**Status:** Fixed. `bin/archive-cli.py` is rewritten with `argparse` subcommands; the old optparse flags are removed (breaking change, chosen deliberately).

- **Commands:** `store FILE`, `get UUID`, `hash UUID`, `list`, `delete UUID`, `health`. Common options are `-u/-c/-k/-a/-m/--timeout` and `-j/-p/-v`. Connection settings fall back to `ARCHIVE_URL`, `ARCHIVE_CERT`, `ARCHIVE_KEY`, `ARCHIVE_CA`, `ARCHIVE_BUCKET`, `ARCHIVE_MODE` and `ARCHIVE_TIMEOUT`.
- **All listed bugs fixed:**
  - `get` reads the right fields and downloads to a `.part` file, keeping it only if the hashes match.
  - The default bucket is `other`.
  - Exit codes: 0 ok, 1 server/hash error, 2 usage error.
  - Client cert and CA are optional (system CAs by default), so it works with `ARCHIVE_CLIENT_CERT=off`.
  - 30 s timeout; quiet by default; no more crashes on `-s -x` without a file or `r.json`; files are closed properly.
  - `get` won't overwrite unless `-f`.
- **Chunked sha256 (1 MB)** in the client and in the server's `calc_hash_from_file`.
- **Several servers:** repeat `--url`, or comma/space separated `ARCHIVE_URL`.
  - `--mode first` (default, clustered servers): use the first server that works; errors move on to the next.
  - `--mode all` (standalone servers): `store`, `list` and `health` run on every server. Exit 0 only if all succeed. `store` lines get `;server:<url>`, since each server has its own uuid. `--delete-local` only deletes the local file when every server has it.
  - `get`, `hash` and `delete` always use the first server that has the uuid.
- **`bin/archive-cli.sh` removed:** its failover now lives in the client. (The packaging scripts were removed later, §7.)
- **`docs/client.md` rewritten.**
- **Tested:**
  - All commands and error paths against a local server, including a 50 MB store/get.
  - `first` and `all` modes with two standalone servers and a dead one.
  - TLS in Docker with a client cert, without one, and with `ARCHIVE_CLIENT_CERT=off`.
- ✅ The server status codes seen during testing (missing file → 500, deleting a missing file → 403) are fixed in §6.

Original findings:

- **`--get` always crashes.** It reads `uuid` and `server_hash` from the hash endpoint, which actually returns `filename` and `hash_remote`, so you get a `KeyError`.
- **The default bucket is `"default"`,** which isn't in the bucket list, so every call without `-b` gets a 403.
- **It exits with code 0 even on failure,** so the failover loop in `archive-cli.sh` never moves on to the next server.
- `archive-cli.sh` uses `conf/test-cert/` but the directory is `conf/test-certs/`, and `${AR_SRV1_URL[$i]}` is a typo.
- Ease of use: switch from `optparse` to `argparse` with subcommands (`archive store FILE -b cert`, `archive get UUID -o out`). Read `ARCHIVE_URL`, `ARCHIVE_CERT`, `ARCHIVE_KEY` and `ARCHIVE_CA` from the environment so you don't pass four flags every time. Hash files in chunks instead of reading them fully into memory.

## 6. Server code quality ✅ DONE

- ✅ **DONE – Duplicated code:** five handlers repeat the same `remote_addr` and bucket/date validation. Pull that into one helper, which is also where the security fixes in §3 go.
  - **Refactored** `app/main/archive.py` from 531 to 302 lines with no behaviour change:
    - `respond(module, status, message, **extra)` replaces the repeated four-line `retdata` blocks.
    - `client_path(module, bucket, date, filename)` runs every check in one place: bucket allowed, date/uuid format, valid client IP. It returns `<upload dir>/<ip>/...`; a new endpoint can't skip a security check.
    - `check_bucket()` does the bucket check alone; `delete` needs it before the allow-remove check.
    - Failed checks raise `RequestError`, and the `@handle_request_errors` decorator returns its response.
  - **Dead code removed:**
    - `request.method != 'POST'` (the route only allows POST).
    - `bucket/date/filename is None` checks (the route guarantees them).
    - `file is None` (unreachable) and the no-op `secure_filename(uuid4())`.
    - The `#!` line in the module.
  - **Shadowing reduced:** the local `hash` variables are now `file_hash` / `calc_hash_from_file(...)`. (The endpoint functions were renamed afterwards, see "Builtins shadowed".)
  - **Verified:** before and after, 88 requests in a fixed set covering every endpoint, success and each error and security case, with delete on and off. Responses (status + body) are identical, with uuids and timestamps masked. `flask doc printdoc` still prints all 6 sections.
  - The wrong status codes and the health `open()` outside `try` were deliberately left unchanged here, to keep this a pure refactor. Both were fixed next (below).
- ✅ **DONE – Status codes:**
  - Use 400 for missing or invalid input, not 500.
  - Use 404 for missing files; `get` and `hash` currently return 500.
  - The `file is None` check in `store` never runs, because `request.files['file']` raises an error first. Use `.get()`.
  - **Fixed:**
    - store: missing bucket → 400 (was 500); missing file → 400 JSON "File is required" (was an HTML 400, now via `request.files.get`).
    - get, hash, delete: missing file → 404 "File not found" (was 500 / 500 / 403).
    - list: nothing stored yet → 200 `[]` (was 500 "No files found").
    - health: unhealthy → 503 with a reason (was 500).
  - **JSON for every error:** `app_errorhandler`s return `{"module": "error", "status_code", "message"}` for Flask's own errors (404 unknown URL, 405 wrong method, 413…). Unhandled exceptions give a JSON 500 "Internal server error", with the traceback in the log.
  - **API docs:** the docstrings now state each endpoint's URL and status codes, and a "Responses" section (`API_RESPONSES_DOC`) lists all codes. `flask doc printdoc` prints clean markdown, and `docs/api-doc.md` is regenerated from it. Startup/config messages now go to stderr, so `flask doc printdoc > docs/api-doc.md` works directly.
  - **Tested:** 29 checks of status code + JSON body, all passing. They cover every endpoint, wrong methods, an unknown URL, a read-only archive (store → JSON 500, health → 503) and a missing archive (health → 503). The client handles the new codes: an empty list exits 0, a missing file exits 1, and failover moves on after a 404.
  - Breaking for scripts that check for the old 500/403 codes; the bundled client only checks for 200.
- ✅ **DONE – Builtins shadowed:** `list` and `hash` are used as function names.
  - **Fixed:** the endpoint functions are renamed `list_files` and `hash_file`; the local `hash` variables were already renamed in the refactor. URLs, responses (including `"module": "list"/"hash"`) and `docs/api-doc.md` are unchanged.
  - Only the Flask endpoint names change (`archive.list_files` / `archive.hash_file`); nothing uses `url_for`.
  - Verified: `list`/`hash` in the module are Python's built-ins again, and the hash and list endpoints return 200 as before.
- ✅ **DONE – Health check:** in `health`, the `open()` sits outside the `try`, so a write error gives a 500 traceback instead of the JSON error.
  - **Fixed together with the status codes:** writing is inside the `try`, and failures give a 503 with a reason.
  - It also missed a read-only archive: it rewrote the existing `health.check` file, which still works in a read-only directory. It now creates and removes a new temporary file (`.health-*`), the same operation `store` needs, so no file is left in the archive.
- ✅ **DONE – CLI not registered:** `archive-service.py` doesn't call `cli.register()`, so `flask doc printdoc` only works through the WSGI entry point.
  - **Fixed** by merging the entry points. Apache/mod_wsgi is no longer used, so `archive.wsgi` and `conf/httpd-archive.conf` are removed.
  - `archive-service.py` is now the only entry point (gunicorn `archive-service:app`, `FLASK_APP`) and calls `cli.register(app)`. The empty `shell_context_processor` is dropped.
  - Tested: `flask doc printdoc` prints all 6 sections, locally and in the Docker image; gunicorn and the container answer 200.
- ✅ **DONE – No upload size limit:** a client could fill the disk.
  - **Fixed:** new `ARCHIVE_MAX_UPLOAD_MB` (default 1024, `0` = no limit) sets Flask's `MAX_CONTENT_LENGTH`. Larger uploads get a JSON 413 "Upload too large, the limit is N MB". Documented in the README table, the example config, the store docstring and `docs/api-doc.md`; `docker-compose.yml` passes it through.
  - Tested: with a 1 MB limit, 512 KB → 200 and 2 MB → 413, also over real HTTP through gunicorn in Docker (curl and the client, which exits 1 with the message). A limit of 0 allows 2 MB. Bad values stop startup.
- ✅ **DONE – Log rotation too small / no logs in `docker logs`:** the log file rotated at 10 KB × 10 files (100 KB of history), and request logs only went to the file.
  - **Fixed** in `app/log/log.py`:
    - `ARCHIVE_LOG_MAX_MB` (default 10, `0` = never rotate) and `ARCHIVE_LOG_BACKUPS` (default 10) set the rotation.
    - `ARCHIVE_LOG_STDERR` also logs to stderr; it is on in the Docker image, so `docker logs` shows requests.
    - `ARCHIVE_LOG_FILE=""` disables the file, and stderr is used if no other output is set.
    - The log dir is created with `makedirs`.
  - Tested: with 1 MB × 2, the files roll at 1 MB and never more than 2 old ones are kept. Handlers are file only by default, file + stderr with `ARCHIVE_LOG_STDERR=true`, and stderr only with an empty `ARCHIVE_LOG_FILE` (no log dir created). In Docker, `docker logs` shows the request lines.
  - Two follow-ups found here (log lines not valid JSON, gunicorn timeout on large uploads) are moved to §10.

## 7. Packaging ✅ DONE

- ✅ **DONE – `make-deb-srv.sh` packaging paths.** It copied `files/` and `logs/`, which are gitignored and may not exist. It installed to `/var/www/apps/archive`, but `gunicorn-start.sh` only looks in `/archive-service` or `/opt/archive-service`.
  - **Fixed** (done with the Apache removal): the package now installs to `/opt/archive-service`, which `gunicorn-start.sh` finds. It no longer copies `files/`, `logs/` or `archive.wsgi`, but adds `requirements.txt`. The unused `tmp/etc` and `tmp/opt/archive` dirs are gone.
  - **Superseded:** both packaging scripts (`bin/make-deb-srv.sh` and `bin/make-rpm-cli.sh`) were later removed. Docker is the supported way to run the server; the client is a single script plus `requirements-cli.txt`.



## 8. automated test suite ✅ DONE

each api endpoint should have a test and they should be easy to run

**Status:** Done. 162 tests, all passing, about 14 s (the fast tests alone about 1.5 s).

- **Run locally:** `./run-tests.sh`. It creates `.venv` on the first run, installs `requirements-dev.txt` (again only when a requirements file changed) and passes its arguments to pytest:
  - `./run-tests.sh -m "not integration"` runs only the fast tests, no real servers.
  - `./run-tests.sh -k delete` runs tests with "delete" in the name.
- **Files:** `requirements-dev.txt` (server + client requirements + pytest), `pytest.ini`, `tests/`:
  - `conftest.py`: `make_app(**settings)` builds an app with test settings in a temp dir. `api` wraps the test client with the client IP. `start_server` starts real gunicorn processes. `ARCHIVE_*` variables from your own environment are removed so they can't affect the tests.
  - `test_store.py`, `test_get_hash.py`, `test_delete.py`, `test_list.py`, `test_health.py`: every endpoint's success and error cases with their status codes, upload limit, `ARCHIVE_TZ` date folders.
  - `test_security.py`: the §3 fixes. `X-Forwarded-For` spoofing (get, store, list `/etc`, health IP), proxy count and rightmost entry, invalid client address, `..` in bucket/date/uuid, exact bucket and health-IP matching.
  - `test_errors.py`: JSON for 404, 405 and unhandled 500.
  - `test_config.py`: `to_bool`/`to_list`, types after parsing, bad values stop startup, config file override, environment variables (reloads the config module), old/new log file names, secrets hidden in the startup output.
  - `test_logging.py`: file/stderr handlers, rotation settings, debug level.
  - `test_apidoc.py`: fails if `docs/api-doc.md` doesn't match `flask doc printdoc`.
  - `test_client.py` (integration): `bin/archive-cli.py` against two real gunicorn servers. Every command, exit codes, usage errors, JSON, `--delete-local`, environment settings, a dead server, `first`/`all` modes.
  - `test_gunicorn_start.py` (integration): `gunicorn-start.sh` run from a temp copy. Every config that must refuse to start, an unwritable archive, plain HTTP, and TLS with generated certs: client cert required (valid → 200, none or another CA → rejected) and `ARCHIVE_CLIENT_CERT=off`.
- **The tests catch regressions:** with the old "trust `X-Forwarded-For`" bug put back, 6 tests fail; with substring bucket matching, 11 fail. Both were restored afterwards.
- **GitHub Actions** (`.github/workflows/tests.yml`, on every push and pull request):
  - `pytest` job on Python 3.11, 3.12 and 3.13.
  - `docker` job: builds the image, starts it with bind mounts, stores and gets `README.md` with the client, checks the file is on the host, and shows `docker logs`.
  - Checked locally: the YAML parses, the docker job's steps pass, and the suite passes on Python 3.11 in a `python:3.11-slim` container (159 passed, 3 skipped because the container runs as root).
- `.dockerignore` now also excludes `tests/`, `.venv/`, `.github/` and the other dev files.
- Problems found while writing the tests are in §10.


## 9. documentation ✅ DONE

update documentation to match new updates
maybe new layout, material for mkdocs with Dockerfile

**Status:** Done. The docs are rewritten to match the current code, and built as a site with Material for MkDocs.

- **README:** now a short entry page: what it is, a quick start (docker compose, without Docker, and the client), links to every doc page, and the tests. The settings tables moved to `docs/configuration.md`.
- **`docs/` pages** (the site navigation is in `mkdocs.yml`):
  - `index.md` (was `docs/README.md`): overview, storage layout `<upload dir>/<ip>/<bucket>/<date>/<uuid>`, quick start. The default buckets and the `ARCHIVE_TZ` date are now correct.
  - `run-server.md`: **rewritten**; the CentOS 7/Python 3.5/`archive-srv.py` text is gone. Covers a venv install, `gunicorn-start.sh` with `INSTALL_PATH` (the workaround for the §10 bug), the start-script settings table, the large-upload timeout note, and Flask's dev server.
  - `docker.md`: compose and `docker run`, settings via env or a mounted config file, health check from the host (gateway IP), developer mode. TLS moved to its own page.
  - `configuration.md` (was `config-server.md`): all `ARCHIVE_*` settings in one table, list/boolean formats, the config file, client address and reverse proxies.
  - `tls.md` (new): TLS and client-cert options with a table of what each combination does, Docker and client examples, the test certs, and the Python 3.13 CA requirement.
  - `client.md`: headings fixed for the site, old `archive-cli.sh` note removed.
  - `api-doc.md`: unchanged (generated, checked by a test).
  - `development.md` (new): running the tests, CI, regenerating the API docs, building the docs.
- **MkDocs:**
  - `mkdocs.yml` uses the Material theme with light/dark mode, code copy buttons and search.
  - `requirements-docs.txt` pins `mkdocs<2`: Material for MkDocs warns at build time that MkDocs 2.0 will break all themes and plugins.
  - `Dockerfile.docs`: `docker run ... archive-service-docs` gives a live preview on port 8000; `... build --strict` builds `site/` (gitignored).
  - A `docs` job in the workflow runs `mkdocs build --strict`, so broken links fail CI.
- **`.gitignore`:** `archive.pid`, `cert.pem`, `key.pem` and `ca.pem` in the repo root are now ignored. `gunicorn-start.sh` writes them there when run from the repo, and a private key could otherwise be committed by accident.
- **Verified:**
  - The site builds with `--strict` (no warnings or broken links), and the live preview serves all 8 pages.
  - The documented commands work: local start with `INSTALL_PATH` (200), Docker developer mode (200), health from the host with the gateway IP allowed (ALLOK).
  - All 162 tests still pass.
- Not done: publishing the site (eg. `mkdocs gh-deploy` to GitHub Pages). That publishes to an external service, so it's left for you to decide.


## 10. Fixes ✅ DONE

Small open items, and problems found while writing the test suite (§8).

- ✅ **Log lines are not valid JSON** (from §6 log rotation): the log format put the message inside a JSON string without escaping, so lines with quotes (all response logs) broke JSON parsing.
  - **Fixed:** a `JsonFormatter` in `app/log/log.py` builds each line with `json.dumps` (`time`, `name`, `loglevel`, `message`, plus `exception` with the traceback when there is one).
  - Tested: every line in the log file parses as JSON, including response logs and an exception with quotes. In Docker, all `docker logs` request lines parse.
- ✅ **gunicorn worker timeout on large uploads** (from §6 log rotation): gunicorn's default 30 s worker timeout could kill large uploads on slow links, while the upload limit is 1024 MB.
  - **Fixed:** `gunicorn-start.sh` passes `--timeout ${TIMEOUT:-300}`; non-numeric values are refused.
  - Tested: the running gunicorn's command line has `--timeout 300` by default and `60` with `TIMEOUT=60`.
- ✅ **TLS files in the container layer** (from §2): in TLS mode `gunicorn-start.sh` wrote `cert.pem`, `key.pem` and `ca.pem` into `/archive-service`.
  - **Fixed:** they are written to a new private dir (700, files 600) in `/dev/shm`, which is in memory, falling back to `/tmp`. `TLS_DIR` overrides the location. The pid file stays in the install dir; it isn't sensitive.
  - Tested: in Docker, TLS with the test client cert → 200, no `.pem` files in `/archive-service`, and the files in `/dev/shm/archive-service-tls.*` are 700/600. The pytest suite checks the default `/dev/shm` location, `TLS_DIR` and the permissions.
- ✅ **`gunicorn-start.sh` doesn't work outside Docker** (found in §8): run from anywhere other than `/archive-service` or `/opt/archive-service` without `INSTALL_PATH`, the install path was empty, gunicorn wrote its pid file to `/` and failed.
  - **Fixed:** `INSTALL_PATH` defaults to the script's own directory (the same as before inside Docker).
  - Tested: started from another directory without `INSTALL_PATH` → 200. The README quick start (`./gunicorn-start.sh` from the repo) works; the `INSTALL_PATH` workaround is removed from the README and `docs/run-server.md`.
- ✅ **`gunicorn-start.sh` writes cert files before checking the settings** (found in §8): eg. `CERT` without `KEY` was refused, but `cert.pem` had already been written.
  - **Fixed:** the script checks every setting first (client-cert option, `PORT`/`TIMEOUT` numbers, writable dirs, TLS combination) and only then writes anything.
  - Tested: for every refused configuration, no `.pem` file appears in the install dir and the `TLS_DIR` is not created.
- **Docs:** `docs/run-server.md` (`TIMEOUT` and `TLS_DIR` in the settings table, new `INSTALL_PATH` default, large-upload note), `docs/tls.md` (where the cert files go) and the README quick start are updated. The `.gitignore` now ignores `/*.pem` in the repo root ("never commit keys"), plus `/archive.pid`.
- All 171 tests pass (9 new for these fixes), and the docs build with `--strict`.

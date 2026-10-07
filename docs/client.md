# Client

The client is not strictly needed, but simplifies interacting with the server.
The protocol is plain HTTP(S), see [API](api-doc.md).

Install the dependencies:

```
pip install -r requirements-cli.txt
```

## Usage

```
archive-cli.py store FILE   [-b BUCKET] [-x] [--syslog]
archive-cli.py get UUID     [-b BUCKET] [-t DATE] [-o OUTPUT] [-f]
archive-cli.py hash UUID    [-b BUCKET] [-t DATE]
archive-cli.py list         [-b BUCKET [-t DATE]]
archive-cli.py delete UUID  [-b BUCKET] [-t DATE]
archive-cli.py health
```

Run `archive-cli.py <command> --help` for all options.

## Connection settings

Every command takes these options, or reads them from the environment:

| Option | Environment | Description |
|---|---|---|
| `-u`, `--url` | `ARCHIVE_URL` | url of the archive service (required), see [several servers](#several-servers) |
| `-c`, `--cert` | `ARCHIVE_CERT` | client cert (PEM), only if the server requires client certs |
| `-k`, `--key` | `ARCHIVE_KEY` | client key (PEM) |
| `-a`, `--ca` | `ARCHIVE_CA` | CA cert (PEM) to verify the server, default the system CAs |
| `-b`, `--bucket` | `ARCHIVE_BUCKET` | bucket, default `other` |
| `-m`, `--mode` | `ARCHIVE_MODE` | `first` (default) or `all`, see [several servers](#several-servers) |
| `--timeout` | `ARCHIVE_TIMEOUT` | request timeout in seconds, default 30 |

Output options: `-j/--json` prints the server response as json, `-p/--pretty`
pretty prints it, `-v/--verbose` prints debug output on stderr.

`-t/--date` defaults to today, use the date returned when the file was stored.

**Exit codes:** 0 ok, 1 server or hash error (on all servers), 2 usage error.

Set the connection once:

```
export ARCHIVE_URL=https://archive-server.test.gazonk.se:8080
export ARCHIVE_CERT=conf/test-certs/archive-client.test.gazonk.se.crt
export ARCHIVE_KEY=conf/test-certs/archive-client.test.gazonk.se.key
export ARCHIVE_CA=conf/test-certs/ca.pem
```

## Store a file

```
$ echo "foo" > dummy.file
$ archive-cli.py store dummy.file -b other
file archived OK;file:dummy.file;uuid:f71f4bd0-22de-474e-8554-81f381e766ed;bucket:other;date:2026-10-06;hash:b5bb9d80...
```

The client compares its own sha256 of the file with the hash the server
returns, if they don't match it exits with code 1.

Add `-x` / `--delete-local` to delete the local file once it is archived and
the hashes match.

## Get a file

```
$ archive-cli.py get f71f4bd0-22de-474e-8554-81f381e766ed -b other -t 2026-10-06 -o dummy.file
file downloaded OK;file:dummy.file;uuid:f71f4bd0-...;bucket:other;date:2026-10-06;hash:b5bb9d80...
```

The file is only written if its hash matches the hash on the server. Without
`-o` it is saved under the uuid, existing files are only overwritten with
`-f` / `--force`.

## Hash of a file in the archive

```
archive-cli.py hash f71f4bd0-22de-474e-8554-81f381e766ed -b other -t 2026-10-06
```

## List

```
archive-cli.py list                          # buckets
archive-cli.py list -b other                 # dates in a bucket
archive-cli.py list -b other -t 2026-10-06   # files (uuids) on a date
```

## Delete

Only works if the server has `ARCHIVE_ALLOW_REMOVE=true`.

```
archive-cli.py delete f71f4bd0-22de-474e-8554-81f381e766ed -b other -t 2026-10-06
```

## Health

Only answers to ips in `ARCHIVE_IPS_HEALTH` on the server.

```
archive-cli.py health
```

## Several servers

Give `--url` more than once, or several urls in `ARCHIVE_URL` (comma or space
separated). How they are used depends on `-m/--mode` (or `ARCHIVE_MODE`):

| Mode | For | `store`, `list`, `health` | `get`, `hash`, `delete` |
|---|---|---|---|
| `first` (default) | clustered servers sharing storage | first server that works | first server that has the file |
| `all` | standalone servers | run on **every** server | first server that has the file |

`get`, `hash` and `delete` use the uuid of a file, each standalone server
gives the file its own uuid, so they always use the first server that has it.

**first:** the servers are tried in order and the client stops at the first
one that works, a connection or TLS error, an error from the server or a hash
mismatch moves on to the next server. Errors are printed on stderr, the server
that worked is printed on stderr as `server: <url>`. Exit code 1 only if all
servers failed.

```
export ARCHIVE_URL="https://archive1:8080,https://archive2:8080"
archive-cli.py store dummy.file -b cert
```

**all:** the file is stored on every server, the output has one line per
server with the server added, as each server has its own uuid:

```
$ archive-cli.py store dummy.file -b cert --mode all
file archived OK;file:dummy.file;uuid:4c1f...;bucket:cert;date:2026-10-06;hash:b5bb...;server:https://archive1:8080
file archived OK;file:dummy.file;uuid:9e02...;bucket:cert;date:2026-10-06;hash:b5bb...;server:https://archive2:8080
```

Exit code 0 only if **all** servers stored the file, if any server failed the
exit code is 1 and the failed servers are listed on stderr.
`--delete-local` only deletes the local file when every server has it.
`list` and `health` print one result per server, `health` exits 1 if any server
is not healthy. With `--json` the output is
`{"mode": "all", "results": [{"server": ..., "status": "ok", "response": ...}, ...]}`.

# Archive service API

## Responses

All responses except a successful `get` (the file) and `list` (a json list)
are json objects:

    {"module": "<endpoint>", "status_code": <code>, "message": "<text>", ...}

Status codes used by all endpoints:

* 200 ok
* 400 bad request: missing or invalid parameter, invalid client address
* 403 forbidden: bucket not allowed, delete not enabled, not allowed to
  call health, or a cross-site request from a browser (a request that
  changes data with an `Origin` header from another site)
* 404 not found: the file does not exist, or unknown url
* 405 method not allowed
* 413 the upload is larger than ARCHIVE_MAX_UPLOAD_MB
* 500 internal server error
* 503 health check failed

## info `GET /archive/info/v1`

returns 200 with the settings a client needs: the allowed buckets, if
delete is enabled, the upload limit in MB (0 = no limit) and the client
address the server sees, files are stored per client address.

## store `POST /archive/store/v1`

takes two parameters in a multipart POST:

* bucket - one of the allowed bucket names
* file - the file to archive, it is stored under a new uuid, the original
  file name is kept in the metadata

returns 200 with the uuid, bucket, date, sha256 (server_hash), name and
size of the stored file, the uuid and date are needed to get the file back.
400 if bucket or file is missing, 403 if the bucket is not allowed,
413 if the file is larger than ARCHIVE_MAX_UPLOAD_MB.

## get `GET /archive/get/v1/<bucket>/<date>/<uuid>`

* bucket - where the file was stored
* date - when the file was stored, YYYY-MM-DD
* uuid - returned by store

returns 200 with the file, 404 if there is no such file.

## hash `GET /archive/hash/v1/<bucket>/<date>/<uuid>`

* bucket - where the file was stored
* date - when the file was stored, YYYY-MM-DD
* uuid - returned by store

returns 200 with the sha256 of the file (hash_remote), 404 if there is no
such file.

## list `GET /archive/list/v1/[<bucket>/[<date>/]]`

* `/archive/list/v1/` - the buckets the client has stored files in
* `/archive/list/v1/<bucket>/` - the dates in a bucket
* `/archive/list/v1/<bucket>/<date>/` - the uuids stored on a date
* `/archive/list/v1/<bucket>/<date>/?details=1` - the files stored on a
  date as objects with uuid, name, size, sha256 and stored (time), name,
  sha256 and stored are null for files stored before metadata was kept

returns 200 with a json list, an empty list if nothing is stored.

## delete `DELETE /archive/delete/v1/<bucket>/<date>/<uuid>`

must be enabled on the server with ARCHIVE_ALLOW_REMOVE=true (default off)

* bucket - where the file was stored
* date - when the file was stored, YYYY-MM-DD
* uuid - returned by store

returns 200 with the sha256 (hash_remote) of the deleted file, 403 if delete
is not enabled, 404 if there is no such file.

## health `GET /archive/health/v1/`

only allowed from the ips in ARCHIVE_IPS_HEALTH, checks that a file can
be written to the archive.

returns 200 with message ALLOK if healthy, 403 if the client is not
allowed, 503 with message ERROR and the reason if the check fails.


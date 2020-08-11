
archive service
---------------

simple service to archive files

functions:

* /archive/store/v1/   - send a file to the archive
* /archive/get/v1/     - download a file from the archive
* /archive/hash/v1/    - get the hash (sha256) of a file in the archive
* /archive/list/v1/    - list content in the archive
* /archive/delete/v1/  - delete content in the archive

common arguments

* bucket where the file was stored (one of the allowed bucket names)
* date when the file was stored (has to be formated YYYY-MM-DD)
* filename is the uuid(4) received by the server when storing files

Service config
--------------

* Edit conf/serviceconfig.py or us environment variables from below

```
SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess'
ARCHIVE_TZ = os.environ.get('ARCHIVE_TZ') or "Europe/Stockholm"
UPLOAD_FOLDER = os.environ.get('ARCHIVE_ULDIR') or "/home/han/devel/archive-service/files"
ALLOWED_BUCKETS = os.environ.get('ARCHIVE_BUCKETS') or ["cert", "other", "log", "config", "admin", "backups"]
ALLOWED_IPS_HEALTH = os.environ.get('ARCHIVE_IPS_HEALTH') or ["127.0.0.1", "127.0.0.2"]
ALLOWREMOVE = os.environ.get('ARCHIVE_ALLOWREMOVE') or 1
DEBUG = os.environ.get('ARCHIVE_DEBUG') or 0
LOG_FILE = os.environ.get('ARCHIVE_LOGFILE') or "logs/archive-service.log"
```

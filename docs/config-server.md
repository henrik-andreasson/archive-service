
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

* check conf/defaultserviceconfig.py to see the defaults then use environment variables or a file:
* optional file conf/archive-service-config.py

```
ARCHIVE_SECRET_KEY = os.environ.get('ARCHIVE_SECRET_KEY') or 'you-will-never-guess'
ARCHIVE_TZ = os.environ.get('ARCHIVE_TZ') or "Europe/Stockholm"
ARCHIVE_UPLOAD_DIR = os.environ.get('ARCHIVE_UPLOAD_DIR') or "/home/han/devel/archive-service/files"
ARCHIVE_BUCKETS = os.environ.get('ARCHIVE_BUCKETS') or ["cert", "other", "log", "config", "admin", "backups"]
ARCHIVE_IPS_HEALTH = os.environ.get('ARCHIVE_IPS_HEALTH') or ["127.0.0.1", "127.0.0.2"]
ARCHIVE_ALLOW_REMOVE = os.environ.get('ARCHIVE_ALLOW_REMOVE') or 1
ARCHIVE_DEBUG = os.environ.get('ARCHIVE_DEBUG') or 0
ARCHIVE_LOG_FILE = os.environ.get('ARCHIVE_LOGFILE') or "logs/archive-service.log"
ARCHIVE_LOG_DIR = os.environ.get('ARCHIVE_LOG_DIR') or "/tmp"

```

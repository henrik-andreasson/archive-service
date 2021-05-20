import os

basedir = os.path.abspath(os.path.dirname(__file__))


class Config(object):
    ARCHIVE_SECRET_KEY = os.environ.get('ARCHIVE_SECRET_KEY') or 'you-will-never-guess'
    ARCHIVE_TZ = os.environ.get('ARCHIVE_TZ') or "Europe/Stockholm"
    ARCHIVE_UPLOAD_DIR = os.environ.get('ARCHIVE_UPLOAD_DIR') or "/tmp"
    ARCHIVE_BUCKETS = os.environ.get('ARCHIVE_BUCKETS') or ["cert", "other", "log", "config", "admin", "backups"]
    ARCHIVE_IPS_HEALTH = os.environ.get('ARCHIVE_IPS_HEALTH') or ["127.0.0.1", "127.0.0.2"]
    ARCHIVE_ALLOW_REMOVE = os.environ.get('ARCHIVE_ALLOW_REMOVE') or 1
    ARCHIVE_DEBUG = os.environ.get('ARCHIVE_DEBUG') or 0
    ARCHIVE_LOG_DIR = os.environ.get('ARCHIVE_LOG_DIR') or "/tmp"
    ARCHIVE_LOGFILE = os.environ.get('ARCHIVE_LOGFILE') or "archive-service.log"

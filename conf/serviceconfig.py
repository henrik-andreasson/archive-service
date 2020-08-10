import os

basedir = os.path.abspath(os.path.dirname(__file__))


class Config(object):
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess'
    ARCHIVE_TZ = os.environ.get('ARCHIVE_TZ') or "Europe/Stockholm"
    UPLOAD_FOLDER = os.environ.get('ARCHIVE_ULDIR') or "/home/han/devel/archive-service/files"
    ALLOWED_BUCKETS = os.environ.get('ARCHIVE_BUCKETS') or ["cert", "other", "log", "config", "admin", "backups"]
    ALLOWED_IPS_HEALTH = os.environ.get('ARCHIVE_IPS_HEALTH') or ["127.0.0.1", "127.0.0.2"]
    ALLOWREMOVE = os.environ.get('ARCHIVE_ALLOWREMOVE') or 1
    DEBUG = os.environ.get('ARCHIVE_DEBUG') or 0
    LOG_FILE = os.environ.get('ARCHIVE_LOGFILE') or "/home/han/devel/archive-service/logs/archive-service.log"

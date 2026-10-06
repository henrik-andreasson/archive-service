import os
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

basedir = os.path.abspath(os.path.dirname(__file__))


def to_bool(value):
    """true/yes/on/1 (any case) is True, everything else is False"""
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def to_list(value):
    """comma separated string or list -> list of stripped strings

    'cert, other' and '"cert","other"' both give ['cert', 'other'], so
    membership tests are exact matches and not substring matches
    """
    if isinstance(value, str):
        value = value.split(',')
    items = (str(v).strip().strip('"\'').strip() for v in value)
    return [v for v in items if v]


class Config(object):
    """defaults, overridden by environment variables with the same name"""
    # optional python file with settings, overrides the environment
    ARCHIVE_CONFIG = os.environ.get('ARCHIVE_CONFIG') or os.path.join(basedir, 'archive-service-config.py')
    # time zone used for the date dirs, eg. archive/<ip>/<bucket>/2026-10-06/
    ARCHIVE_TZ = os.environ.get('ARCHIVE_TZ') or "Europe/Stockholm"
    ARCHIVE_UPLOAD_DIR = os.environ.get('ARCHIVE_UPLOAD_DIR') or "/tmp"
    # comma separated, eg. ARCHIVE_BUCKETS="cert,other"
    ARCHIVE_BUCKETS = os.environ.get('ARCHIVE_BUCKETS') or "cert,other,log,config,admin,backups"
    ARCHIVE_IPS_HEALTH = os.environ.get('ARCHIVE_IPS_HEALTH') or "127.0.0.1,127.0.0.2"
    # delete is off unless explicitly enabled
    ARCHIVE_ALLOW_REMOVE = os.environ.get('ARCHIVE_ALLOW_REMOVE') or "false"
    ARCHIVE_DEBUG = os.environ.get('ARCHIVE_DEBUG') or "false"
    # largest upload in MB, 0 = no limit
    ARCHIVE_MAX_UPLOAD_MB = os.environ.get('ARCHIVE_MAX_UPLOAD_MB') or "1024"
    ARCHIVE_LOG_DIR = os.environ.get('ARCHIVE_LOG_DIR') or "/tmp"
    # empty = no log file, ARCHIVE_LOGFILE is the old name, still accepted
    if 'ARCHIVE_LOG_FILE' in os.environ:
        ARCHIVE_LOG_FILE = os.environ['ARCHIVE_LOG_FILE']
    else:
        ARCHIVE_LOG_FILE = os.environ.get('ARCHIVE_LOGFILE') or "archive-service.log"
    # the log file is rotated at this size (0 = never), keeping this many old files
    ARCHIVE_LOG_MAX_MB = os.environ.get('ARCHIVE_LOG_MAX_MB') or "10"
    ARCHIVE_LOG_BACKUPS = os.environ.get('ARCHIVE_LOG_BACKUPS') or "10"
    # also log to stderr, eg. for docker logs
    ARCHIVE_LOG_STDERR = os.environ.get('ARCHIVE_LOG_STDERR') or "false"
    # number of trusted reverse proxies in front of the service, 0 = none,
    # X-Forwarded-For is ignored unless this is > 0
    ARCHIVE_PROXY_COUNT = os.environ.get('ARCHIVE_PROXY_COUNT') or "0"


def normalize_config(config):
    """convert settings from the environment or the config file to the right
    types, raises ValueError with a readable message on bad values"""
    for key in ('ARCHIVE_BUCKETS', 'ARCHIVE_IPS_HEALTH'):
        config[key] = to_list(config[key])
    for key in ('ARCHIVE_ALLOW_REMOVE', 'ARCHIVE_DEBUG', 'ARCHIVE_LOG_STDERR'):
        config[key] = to_bool(config[key])

    for key in ('ARCHIVE_PROXY_COUNT', 'ARCHIVE_MAX_UPLOAD_MB', 'ARCHIVE_LOG_MAX_MB', 'ARCHIVE_LOG_BACKUPS'):
        try:
            config[key] = int(config[key])
        except ValueError:
            raise ValueError("%s must be a number, got '%s'" % (key, config[key]))
        if config[key] < 0:
            raise ValueError("%s must be 0 or more" % key)

    try:
        ZoneInfo(config['ARCHIVE_TZ'])
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError("ARCHIVE_TZ is not a known time zone: '%s'" % config['ARCHIVE_TZ'])

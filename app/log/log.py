import json
import logging
from logging.handlers import RotatingFileHandler
import os
import sys


class JsonFormatter(logging.Formatter):
    """one json object per line: time, name, loglevel and message"""

    def format(self, record):
        entry = {
            "time": self.formatTime(record),
            "name": record.name,
            "loglevel": record.levelname,
            "message": record.getMessage(),
        }
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry)


def create_logger(app):
    """log to the rotating file ARCHIVE_LOG_DIR/ARCHIVE_LOG_FILE and/or to
    stderr (ARCHIVE_LOG_STDERR), if neither is set stderr is used"""
    handlers = []

    if app.config['ARCHIVE_LOG_FILE']:
        os.makedirs(app.config['ARCHIVE_LOG_DIR'], exist_ok=True)
        file_abs_path = os.path.join(app.config['ARCHIVE_LOG_DIR'], app.config['ARCHIVE_LOG_FILE'])
        handlers.append(RotatingFileHandler(file_abs_path,
                                            maxBytes=app.config['ARCHIVE_LOG_MAX_MB'] * 1024 * 1024,
                                            backupCount=app.config['ARCHIVE_LOG_BACKUPS']))

    if app.config['ARCHIVE_LOG_STDERR'] or not handlers:
        handlers.append(logging.StreamHandler(sys.stderr))

    for handler in list(app.logger.handlers):
        app.logger.removeHandler(handler)

    level = logging.DEBUG if app.config['ARCHIVE_DEBUG'] else logging.INFO
    for handler in handlers:
        handler.setFormatter(JsonFormatter())
        handler.setLevel(level)
        app.logger.addHandler(handler)
    app.logger.setLevel(level)

    app.logger.info('Archive Service startup')

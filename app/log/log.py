import logging
from logging.handlers import RotatingFileHandler
import os


def create_logger(app):
    if not os.path.exists(app.config['ARCHIVE_LOG_DIR']):
        os.mkdir(app.config['ARCHIVE_LOG_DIR'])
    file_abs_path = "%s/%s" % (app.config['ARCHIVE_LOG_DIR'], app.config['ARCHIVE_LOG_FILE'])
    file_handler = RotatingFileHandler(file_abs_path, maxBytes=10240, backupCount=10)

    for handler in app.logger.handlers:
        app.logger.removeHandler(handler)

    app.logger.addHandler(file_handler)

    logstr = """{"time": "%(asctime)s", "name": "%(name)s", "loglevel": "%(levelname)s", "message": "%(message)s"}"""
    file_handler.setFormatter(logging.Formatter(logstr))

    if app.config['DEBUG']:
        file_handler.setLevel(logging.DEBUG)
        app.logger.setLevel(logging.DEBUG)
        app.logger.debug('Archive Service startup')

    else:
        file_handler.setLevel(logging.INFO)
        app.logger.setLevel(logging.INFO)
        app.logger.info('Archive Service startup')

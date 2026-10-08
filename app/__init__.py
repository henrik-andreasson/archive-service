import os
import sys
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix
from conf.defaultserviceconfig import Config, normalize_config
from app.log.log import create_logger


def create_app(config_class=Config):
    # no automatic /static/, the web front-end is only served at /ui/ when enabled
    app = Flask(__name__, static_folder=None)

    print("loading config from defaults and environment (conf/defaultserviceconfig.py)", file=sys.stderr)
    app.config.from_object(config_class)

    config_file = app.config['ARCHIVE_CONFIG']
    if os.path.isfile(config_file):
        print(f"adding config from file {config_file}", file=sys.stderr)
        app.config.from_pyfile(config_file)
    elif os.environ.get('ARCHIVE_CONFIG'):
        raise FileNotFoundError(f"ARCHIVE_CONFIG is set but the file does not exist: {config_file}")
    else:
        print(f"no config file at {config_file}, using defaults and environment", file=sys.stderr)

    normalize_config(app.config)

    # only show the service settings and never print secrets
    for conf in sorted(app.config):
        if not conf.startswith('ARCHIVE_'):
            continue
        if any(word in conf for word in ('SECRET', 'PASSWORD', 'TOKEN')):
            value = '***' if app.config[conf] else '(not set)'
        else:
            value = app.config[conf]
        print(f'conf key: {conf} = {value}', file=sys.stderr)

    # larger uploads get a 413
    max_upload_mb = app.config['ARCHIVE_MAX_UPLOAD_MB']
    app.config['MAX_CONTENT_LENGTH'] = max_upload_mb * 1024 * 1024 if max_upload_mb > 0 else None

    proxy_count = app.config['ARCHIVE_PROXY_COUNT']
    if proxy_count > 0:
        print(f"trusting X-Forwarded-For from {proxy_count} proxy(s)", file=sys.stderr)
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=proxy_count)

    from app.main import bp as main_bp
    app.register_blueprint(main_bp)

    create_logger(app)

    return app

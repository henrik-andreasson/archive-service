from flask import Flask
from flask_bootstrap import Bootstrap
from conf.defaultserviceconfig import Config
from app.log.log import create_logger


bootstrap = Bootstrap()


def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)

    print(f"loading config from build in class conf/defaultserviceconfig.py")
    app.config.from_object(config_class)
    print(f"adding config from optional file conf/archive-service-config.py")
    app.config.from_pyfile('conf/archive-service-config.py', silent=True)
    for conf in app.config:
        print(f'conf key: {conf} = {app.config[conf]}')

    bootstrap.init_app(app)

    from app.main import bp as main_bp
    app.register_blueprint(main_bp)

    create_logger(app)

    return app

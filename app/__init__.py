from flask import Flask
from flask_bootstrap import Bootstrap
from conf.serviceconfig import Config
from app.log.log import create_logger

bootstrap = Bootstrap()


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    bootstrap.init_app(app)

    from app.main import bp as main_bp
    app.register_blueprint(main_bp)

    create_logger(app)

    return app

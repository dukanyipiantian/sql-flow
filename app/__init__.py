from flask import Flask
from config import Config


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    from . import routes
    app.register_blueprint(routes.bp)

    if not app.config['SECRET_KEY']:
        raise ValueError("SECRET_KEY不能为空！请在.env文件中设置")

    return app
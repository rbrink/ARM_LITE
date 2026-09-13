import os
import secrets
from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
from logging.config import dictConfig

import arm_lite.config.config as cfg

sqlitefile = "sqlite:///" + cfg.arm_config.get("DBFILE")

dictConfig({
    'version': 1,
    'formatters': {'default': {
        'format': '[%(asctime)s] %(levelname)s ARM: %(module)s.%(funcName)s %(message)s',
        'datefmt': cfg.arm_config.get("DATE_FORMAT")
    }},
    'handlers': {
        'wsgi': {
            'class': "logging.StreamHandler",
            'stream': 'ext://flask.logging.wsgi_errors_stream',
            'formatter': 'default'
        },
        'console': {'class': "logging.StreamHandler"},
        'null': {'class': "logging.NullHandler"},
    },
    'root': {
        'level': cfg.arm_config.get("LOGLEVEL"),
        'handlers': ['wsgi']
    },
})

app = Flask(__name__)
csrf = CSRFProtect()
csrf.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)

def _get_or_create_secret_key() -> str:
    key = cfg.arm_config.get("FLASK_SECRET_KEY")
    if key:
        return key
    key = secrets.token_hex(32)
    cfg.arm_config["FLASK_SECRET_KEY"] = key
    try:
        cfg.build_config()
    except Exception as e:
        print(f"WARN: Could not persist generated FLASK_SECRET_KEY to arm_lite.yaml: {e}")
    return key

app.config["SECRET_KEY"] = _get_or_create_secret_key()
app.config["SQLALCHEMY_DATABASE_URI"] = sqlitefile
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

from arm_lite.ui import routes
from arm_lite.ui.auth.auth import route_auth
from arm_lite.ui.database.database import route_database
from arm_lite.ui.settings.settings import route_settings
app.register_blueprint(route_auth)
app.register_blueprint(route_database)
app.register_blueprint(route_settings)

import logging
logging.getLogger("werkzeug").setLevel(logging.ERROR)

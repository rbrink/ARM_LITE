import os
import secrets
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
from logging.config import dictConfig

import arm_lite.config.config as cfg
import arm_lite.ui.utils as utils

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

app.config["SECRET_KEY"] = utils.get_or_create_secret_key()
app.config["SQLALCHEMY_DATABASE_URI"] = sqlitefile
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

from arm_lite.ui import routes
from arm_lite.ui.auth.auth import route_auth
from arm_lite.ui.settings.settings import route_settings
app.register_blueprint(route_auth)
app.register_blueprint(route_settings)

import logging
logging.getLogger("werkzeug").setLevel(logging.ERROR)

from flask import Flask
from config import Config
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from sqlalchemy import MetaData
from flask_login import LoginManager
from flask_admin import Admin

import logging


import sqlite3
import numpy as np
import io

sqlite3.register_adapter(np.int64, lambda val: int(val))

convention = {
    "ix": 'ix_%(column_0_label)s',
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}

app = Flask(__name__)
app.config.from_object(Config)

admin = Admin(app, name='fast-catchup', template_mode='bootstrap3')
logging.basicConfig(filename='app.log', filemode='w', level=logging.DEBUG)



metadata = MetaData(naming_convention=convention)
db = SQLAlchemy(app, metadata=metadata)
migrate = Migrate(app, db)
login = LoginManager(app)
login.login_view = 'login'


from webapp import routes, models, admin_views

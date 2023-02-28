import os
import sqlite3

basedir = os.path.abspath(os.path.dirname(__file__))

class Config(object):
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # SQLALCHEMY_ENGINE_OPTIONS = {'detect_types': sqlite3.PARSE_DECLTYPES}
    # SQLALCHEMY_ENGINE_OPTIONS = {'native_datetime': True}
    FLASK_ADMIN_SWATCH = 'cerulean'

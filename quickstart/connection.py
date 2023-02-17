from contextlib import contextmanager

from pathlib import Path
from sqlalchemy import exc


import sys
sys.path.append(str(Path(sys.path[0]).parent))

from app import app, db
from app import models

from flask_login import current_user

@contextmanager
def db_ops(db_name='sqlite:///app.db', model_names=None):
    # Figure out why this context push cause error
    # app.app_context().push()
    # db.session.rollback()

    Models = []
    for m_name in model_names:
        Model = getattr(models, m_name)
        Models.append(Model)
    return_list = []
    return_list.append(db)
    return_list.extend(Models)
    yield tuple(return_list)
    db.session.commit()
    # try:
    #     db.session.commit()
    # except exc.IntegrityError:
    #     db.session.rollback()
    # finally:
        # db.session.close()
def get_current_user():
    return current_user

from contextlib import contextmanager

from pathlib import Path

import sys
sys.path.append(str(Path(sys.path[0]).parent))

from app import app, db
from app import models
# from app.models import SlackUser, SlackChannel, SlackMessage

from flask_login import current_user

@contextmanager
def db_ops(db_name='sqlite:///app.db', model_names=None):
    app.app_context().push()
    db.session.rollback()
    Models = []
    for m_name in model_names:
        Model = getattr(models, m_name)
        Models.append(Model)
    return_list = []
    return_list.append(db)
    return_list.extend(Models)
    yield tuple(return_list)
    db.session.commit()
    db.session.close()

def get_current_user():
    return current_user

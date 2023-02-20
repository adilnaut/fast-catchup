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


def get_platform_id(platform_name):
    # get platform id for slack for current user
    # get current user id
    # get workspace id from user id
    # get platform_id by platform name/hardcoded codename

    current_user = get_current_user()
    user_id = current_user.get_id() if current_user else None

    if current_user:
        # handle case when user is not is_authenticated or put decorator for authcheck
        with db_ops(model_names=['Workspace', 'Platform']) as (db, Workspace, Platform):
            # also may replace this by one sql query
            workspace = Workspace.query.filter_by(user_id=user_id).first()
            if not workspace:
                return None
            platform = Platform.query.filter_by(workspace_id=workspace.id) \
                .filter_by(name=platform_name) \
                .first()
            if not platform:
                return None
            return platform.id

def get_auth_data(platform_name, authdata_name):
    platform_id = get_platform_id(platform_name)
    with db_ops(model_names=['AuthData']) as (db, AuthData):
        token_row = AuthData.query \
            .filter_by(platform_id=platform_id) \
            .filter_by(name=authdata_name) \
            .filter_by(is_data=True) \
            .first()

        auth_data = token_row.file_data
        return auth_data

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

def clear_session_data(session_id=None):
    from app.models import (User, Workspace, AudioFile, Platform, AuthData, PriorityListMethod, PriorityItemMethod,
        PriorityItem, PriorityMessage, PriorityList, Session, SlackChannel, SlackUser, SlackMessage, SlackAttachment,
        SlackLink, GmailMessage, GmailLink, GmailUser, GmailAttachment, GmailMessageTag, GmailMessageText,
        GmailMessageListMetadata, GmailMessageLabel)
    user_id = current_user.get_id()
    workspace = Workspace.query.filter_by(user_id=user_id).first()
    workspace_id = workspace.id
    platforms = Platform.query.filter_by(workspace_id=workspace_id).all()

    # messages and metadata
    for platf in platforms:
        slack_channels = SlackChannel.query.filter_by(platform_id=platf.id).all()
        # print("To start iterating on slack_channels %s" % ', '.join(slack_channels))
        for sc in slack_channels:
            slack_messages = SlackMessage.query.filter_by(slack_channel_id=sc.id) \
                .filter_by(session_id=session_id).all()
            # print("To start iterating on slack_messages %s" % ', '.join(slack_messages))
            for sm in slack_messages:
                slack_attch = SlackAttachment.query.filter_by(slack_message_ts=sm.ts).all()
                # print("To start iterating on slack_attachments %s" % ', '.join(slack_attch))
                for sa in slack_attch:
                    filepath = sa.filepath
                    if filepath and os.path.exists(filepath):
                        os.remove(filepath)
                    db.session.delete(sa)
                slack_links = SlackLink.query.filter_by(slack_message_ts=sm.ts).all()
                # print("To start deleting slack links %s" % ', '.join(slack_links))
                for sl in slack_links:
                    db.session.delete(sl)
                db.session.delete(sm)

        gmail_users = GmailUser.query.filter_by(platform_id=platf.id).all()
        for gu in gmail_users:
            gmail_messages = GmailMessage.query.filter_by(gmail_user_email=gu.email) \
                .filter_by(session_id=session_id).all()
            for gm in gmail_messages:
                g_tags = GmailMessageTag.query.filter_by(gmail_message_id=gm.id).all()
                for g_tag in g_tags:
                    db.session.delete(g_tag)
                g_list_metas = GmailMessageListMetadata.query.filter_by(gmail_message_id=gm.id).all()
                for g_list_meta in g_list_metas:
                    db.session.delete(g_list_meta)
                g_m_texts = GmailMessageText.query.filter_by(gmail_message_id=gm.id).all()
                for g_m_text in g_m_texts:
                    db.session.delete(g_m_text)
                g_m_labels = GmailMessageLabel.query.filter_by(gmail_message_id=gm.id).all()
                for g_m_label in g_m_labels:
                    db.session.delete(g_m_label)
                g_links = GmailLink.query.filter_by(gmail_message_id=gm.id).all()
                for g_link in g_links:
                    db.session.delete(g_link)
                g_attachments = GmailAttachment.query.filter_by(gmail_message_id=gm.id).all()
                for g_a in g_attachments:
                    filepath = g_a.filepath
                    if filepath and os.path.exists(filepath):
                        os.remove(filepath)
                    db.session.delete(g_a)
                db.session.delete(gm)


    # delete priority tables
    p_lists = PriorityList.query.filter_by(platform_id=platf.id) \
        .filter_by(session_id=session_id).all()
    for p_list in p_lists:
        p_items = PriorityItem.query.filter_by(priority_list_id=p_list.id).all()
        for p_item in p_items:
            p_i_methods = PriorityItemMethod.query.filter_by(priority_item_id=p_item.id).all()
            for p_i_m in p_i_methods:
                db.session.delete(p_i_m)
            db.session.delete(p_item)
        db.session.delete(p_list)
    p_messages = PriorityMessage.query.filter_by(platform_id=platf.id) \
        .filter_by(session_id=session_id).all()
    for p_m in p_messages:
        db.session.delete(p_m)

    # attempt to delete session and audio if exists
    session = Session.query.filter_by(session_id=session_id).first()
    audio_file = AudioFile.query.filter_by(session_id=session_id).first()
    if audio_file:
        filepath = audio_file.file_path
        if filepath and os.path.exists(filepath):
            os.remove(filepath)
        db.session.delete(audio_file)
    if session:
        db.session.delete(session)
    db.session.commit()

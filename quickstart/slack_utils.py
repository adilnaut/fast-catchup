import os
from datetime import datetime, timedelta
from dateutil import parser
import pytz
import time
import requests
import hashlib

from collections import OrderedDict


from slack_sdk.errors import SlackApiError
from slack_bolt import App

from quickstart.connection import db_ops, get_current_user, get_platform_id, get_auth_data
from quickstart.gmail_utils import extract_domain
from quickstart.sqlite_utils import get_upsert_query
from quickstart.priority_engine import create_priority_list, update_priority_list_methods, fill_priority_list
from quickstart.platform import get_abstract_for_slack



def etl_channels(app, db):
    # save all conversations
    platform_id = get_platform_id('slack')
    response = app.client.conversations_list(types='public_channel,private_channel,im, mpim')
    status = response.get('ok')
    channels = response.get('channels')
    if status and channels:
        for channel in channels:
            id = channel.get('id')
            name = channel.get('name')
            is_channel = channel.get('is_channel')
            is_group = channel.get('is_group')
            is_im = channel.get('is_im')
            created = channel.get('created')
            creator = channel.get('creator')
            is_archived = channel.get('is_archived')
            is_general = channel.get('is_general')
            unlinked = channel.get('unlinked')
            name_normalized = channel.get('name_normalized')
            is_shared = channel.get('is_shared')
            is_ext_shared = channel.get('is_ext_shared')
            is_org_shared = channel.get('is_org_shared')
            is_pending_ext_shared = channel.get('is_pending_ext_shared')
            is_member = channel.get('is_member')
            is_private = channel.get('is_private')
            is_mipm = channel.get('is_mpim')
            topic = channel.get('topic')
            if topic:
                topic = topic.get('value')
            purpose = channel.get('purpose')
            if purpose:
                purpose = purpose.get('value')
            num_members = channel.get('num_members')
            sc_kwargs = OrderedDict([('id', id)
                            , ('platform_id', platform_id)
                            , ('name', name)
                            , ('is_channel', is_channel)
                            , ('is_group', is_group)
                            , ('is_im', is_im)
                            , ('created', created)
                            , ('creator', creator)
                            , ('is_archived', is_archived)
                            , ('is_general', is_general)
                            , ('unlinked', unlinked)
                            , ('name_normalized', name_normalized)
                            , ('is_shared', is_shared)
                            , ('is_ext_shared', is_ext_shared)
                            , ('is_org_shared', is_org_shared)
                            , ('is_pending_ext_shared', is_pending_ext_shared)
                            , ('is_member', is_member)
                            , ('is_private', is_private)
                            , ('is_mipm', is_mipm)
                            , ('topic', topic)
                            , ('purpose', purpose)
                            , ('num_members', num_members)])
            sc_query = get_upsert_query('slack_channel', sc_kwargs.keys(), 'id, platform_id')
            db.session.execute(sc_query, sc_kwargs)

def etl_users(app, db):
    response = app.client.users_list()
    status = response.get('ok')
    members = response.get('members')
    platform_id = get_platform_id('slack')
    # don't overwhelm API rate
    if status and members:
        for member in members:
            id = member.get('id')
            name = member.get('name')
            team_id = member.get('team_id')
            deleted = member.get('deleted')
            color = member.get('color')
            real_name = member.get('real_name')
            tz = member.get('tz')
            tz_label = member.get('tz_label')
            tz_offset = member.get('tz_offset')
            profile = member.get('profile')
            if profile:
                profile_avatar_hash = profile.get('avatar_hash')
                profile_status_text = profile.get('status_text')
                profile_status_emoji = profile.get('status_emoji')
                profile_real_name = profile.get('real_name')
                profile_display_name = profile.get('display_name')
                profile_real_name_normalized = profile.get('real_name_normalized')
                profile_display_name_normalized = profile.get('display_name_normalized')
                profile_email = profile.get('email')
                profile_image_24 = profile.get('image_24')
                profile_image_32 = profile.get('image_32')
                profile_image_48 = profile.get('image_48')
                profile_image_72 = profile.get('image_72')
                profile_image_192 = profile.get('image_192')
                profile_image_512 = profile.get('image_512')
                profile_team = profile.get('team')
            is_admin = member.get('is_admin')
            is_owner = member.get('is_owner')
            is_primary_owner = member.get('is_primary_owner')
            is_restricted = member.get('is_restricted')
            is_ultra_restricted = member.get('is_ultra_restricted')
            is_bot = member.get('is_bot')
            updated = member.get('updated')
            is_app_user = member.get('is_app_user')
            has_2fa = member.get('has_2fa')
            su_kwargs = OrderedDict([('id', id)
                , ('platform_id', platform_id)
                , ('name', name)
                , ('team_id', team_id)
                , ('deleted', deleted)
                , ('color', color)
                , ('real_name', real_name)
                , ('tz', tz)
                , ('tz_label', tz_label)
                , ('tz_offset', tz_offset)
                , ('profile_avatar_hash', profile_avatar_hash)
                , ('profile_status_text', profile_status_text)
                , ('profile_status_emoji', profile_status_emoji)
                , ('profile_real_name', profile_real_name)
                , ('profile_display_name', profile_display_name)
                , ('profile_real_name_normalized', profile_real_name_normalized)
                , ('profile_display_name_normalized', profile_display_name_normalized)
                , ('profile_email', profile_email)
                , ('profile_image_24', profile_image_24)
                , ('profile_image_32', profile_image_32)
                , ('profile_image_48', profile_image_48)
                , ('profile_image_72', profile_image_72)
                , ('profile_image_192', profile_image_192)
                , ('profile_image_512', profile_image_512)
                , ('profile_team', profile_team)
                , ('is_admin', is_admin)
                , ('is_owner', is_owner)
                , ('is_primary_owner', is_primary_owner)
                , ('is_restricted', is_restricted)
                , ('is_ultra_restricted', is_ultra_restricted)
                , ('is_bot', is_bot)
                , ('updated', updated)
                , ('is_app_user', is_app_user)
                , ('has_2fa', has_2fa)])
            su_query = get_upsert_query('slack_user', su_kwargs.keys(), 'id, platform_id')
            db.session.execute(su_query, su_kwargs)


def etl_messages(app, db, session_id=None, days_ago=1, max_pages=1,  verbose=False):
    # don't overwhelm API rate
    slack_channels = None
    platform_id = get_platform_id('slack')

    with db_ops(model_names=['SlackChannel']) as (db_sess, SlackChannel):
        slack_channels = SlackChannel.query.filter_by(platform_id=platform_id).all()

    yesterday = datetime.utcnow() - timedelta(days=days_ago)
    unix_time = time.mktime(yesterday.timetuple())

    for channel in slack_channels:
        next_cursor = None
        for i in range(max_pages):
            # don't overwhelm API rate
            time.sleep(0.2)
            if verbose:
                print("channel %s, id %s, request number %s" % (channel.name,
                    channel.id, i))
            if next_cursor:
                response = app.client.conversations_history(channel=channel.id, oldest=unix_time,
                    limit=100, cursor=next_cursor)
            else:
                response = app.client.conversations_history(channel=channel.id,
                    oldest=unix_time, include_all_metadata='true', limit=100)
            status = response.get('ok')
            response_metadata = response.get('response_metadata')
            if response_metadata:
                next_cursor = response_metadata.get('next_cursor')
            has_more = response.get('has_more')

            messages = response.get('messages')
            if verbose:
                print("Has more %s, messages %s" % (has_more, len(messages)))
            if status and messages:
                for message in messages:
                    type = message.get('type')
                    user = message.get('user')
                    text = message.get('text')
                    channel_id = message.get('channel')
                    ts = message.get('ts')
                    with db_ops(model_names=['SlackMessage']) as (db_s, SlackMessage):
                        sid = SlackMessage.query.filter_by(ts=ts).first()
                        if sid:
                            continue
                    sm_kwargs = OrderedDict([('ts', ts)
                            , ('type', type)
                            , ('slack_user_id', user)
                            , ('text', text)
                            , ('slack_channel_id', channel.id)
                            , ('session_id', session_id)
                            , ('is_unread', True)])
                    sm_query = get_upsert_query('slack_message', sm_kwargs.keys(), 'ts')
                    db.session.execute(sm_query, sm_kwargs)
                    # this is a list of blocks
                    blocks = message.get('blocks')

                    for block in blocks:
                        block_type = block.get('type')
                        block_id = block.get('block_id')

                        if verbose:
                            print("DEBUG block_type %s" % block_type)
                            print("DEBUG block id %s" % block_id)
                        # this is a list of elements
                        block_sub_elements = block.get('elements')
                        for sub_element in block_sub_elements:
                            block_elements = sub_element.get('elements')
                            for block_element in block_elements:
                                element_type = block_element.get('type')
                                element_text = block_element.get('text')
                                element_url = block_element.get('url')

                                # here ignore all non-url elements,
                                # cause they are already being processed
                                # in the text part
                                if verbose:
                                    print("DEBUG: element_type %s" % element_type)
                                    print("DEBUG: element_text %s" % element_text)
                                    print("DEBUG: element_url %s" % element_url)

                                if not element_url:
                                    continue

                                has_text = element_text is None


                                link_kwargs = OrderedDict([('slack_message_ts', ts)
                                    , ('url', element_url)
                                    , ('has_text', has_text)
                                    , ('text', element_text)
                                    , ('domain', extract_domain(element_url))])
                                link_query = get_upsert_query('slack_link', link_kwargs.keys(), 'slack_message_ts, url')
                                db.session.execute(link_query, link_kwargs)

                    files_data = message.get('files')
                    if not files_data:
                        continue
                    for one_file_data in files_data:
                        slack_app_token = get_auth_data('slack', 'SLACK_BOT_TOKEN')
                        file_id = one_file_data.get('id')

                        file_name = one_file_data.get('name')
                        # get url_private_download from one_file_data
                        file_url = one_file_data.get('url_private')
                        if verbose:
                            print("Downloaded " + file_name)

                        # download file with authorized request (slack_token) to temp store
                        r = requests.get(file_url, headers={'Authorization': 'Bearer %s' % slack_app_token})
                        r.raise_for_status
                        file_data = r.content   # get binary content
                        if verbose:
                            print('File size: %s' % len(file_data))

                        # check bytes content md5 hash first without writing to disk
                        file_md5 = hashlib.md5(file_data).hexdigest()
                        file_extension = one_file_data.get('filetype')

                        workdir_ = 'file_store'
                        filepath_ = os.path.join(workdir_, '%s.%s' % (file_md5, file_extension))
                        # check if hash isn't on fileserver yet
                        is_file_exist = os.path.exists(filepath_)

                        # if not upload to server
                        if not is_file_exist:
                            with open(filepath_, 'wb') as f:
                                f.write(file_data)

                        slack_attachment_kwargs = OrderedDict([('md5', file_md5)
                            , ('slack_message_ts', ts)
                            , ('slack_user_id', user)
                            , ('size', one_file_data.get('size'))
                            , ('created', one_file_data.get('created'))
                            , ('timestamp', one_file_data.get('timestamp'))
                            , ('id', one_file_data.get('id'))
                            , ('filename', one_file_data.get('name'))
                            , ('filepath', filepath_)
                            , ('title', one_file_data.get('title'))
                            , ('mimetype', one_file_data.get('mimetype'))
                            , ('filetype', one_file_data.get('filetype'))
                            , ('pretty_type', one_file_data.get('pretty_type'))
                            , ('user_team', one_file_data.get('user_team'))
                            , ('editable', one_file_data.get('editable'))
                            , ('mode', one_file_data.get('mode'))
                            , ('is_external', one_file_data.get('is_external'))
                            , ('external_type', one_file_data.get('external_type'))
                            , ('is_public', one_file_data.get('is_public'))
                            , ('public_url_shared', one_file_data.get('public_url_shared'))
                            , ('display_as_bot', one_file_data.get('display_as_bot'))
                            , ('username', one_file_data.get('username'))
                            , ('url_private', one_file_data.get('url_private'))
                            , ('url_private_download', one_file_data.get('url_private_download'))
                            , ('media_display_type', one_file_data.get('media_display_type'))
                            , ('thumb_pdf', one_file_data.get('thumb_pdf'))
                            , ('thumb_pdf_w', one_file_data.get('thumb_pdf_w'))
                            , ('thumb_pdf_h', one_file_data.get('thumb_pdf_h'))
                            , ('permalink', one_file_data.get('permalink'))
                            , ('permalink_public', one_file_data.get('permalink_public'))
                            , ('is_starred', one_file_data.get('is_starred'))
                            , ('has_rich_preview', one_file_data.get('has_rich_preview'))
                            , ('file_access', one_file_data.get('file_access'))])
                        sa_query = get_upsert_query('slack_attachment', sa_kwargs.keys(), 'md5')
                        db.session.execute(sa_query, sa_kwargs)
            if not has_more:
                break;


def ts_to_formatted_date(ts):
    # dangerous timstamp handling
    return datetime.fromtimestamp(int(ts.split('.')[0])).strftime('%c')


# todo handle if there are no slack token data in db
def auth_and_load_session_slack():
    app_token = get_auth_data('slack', 'SLACK_BOT_TOKEN')
    app_secret = get_auth_data('slack', 'SLACK_SIGNING_SECRET')
    app = App(
        token=app_token,
        signing_secret=app_secret
    )
    return app



# Opportunity: make it sqllite defined function?
def encapsulate_names_by_ids(text):
    platform_id = get_platform_id('slack')
    if '<@' in text.split('>')[0]:
        left = text.split('>')[0]
        middle = left.split('<@')[1]
        user_data = None
        with db_ops(model_names=['SlackUser']) as (db, SlackUser):
            user_data = SlackUser.query.filter_by(id=middle)  \
                .filter_by(platform_id=platform_id) \
                .first()
        if user_data:
            # user_data = slack_users.get(middle)
            user_name = user_data.name
            # user_data = slack_users.get(middle)
            # user_name = user_data.get('name')
            text = text.replace('<@%s>' % middle, user_name)
    return text

# (message, slack_users, slack_conversation)
def format_slack_message(slack_message):
    text = slack_message.text
    # text = slack_message.get('text')
    user_id = slack_message.slack_user_id
    # user_id = slack_message.get('slack_user_id')
    channel_id = slack_message.slack_channel_id
    # channel_id = slack_message.get('slack_channel_id')
    ts = slack_message.ts
    # ts = slack_message.get('ts')

    # old
    # get user name
    # user_data = slack_users.get(user_id)
    user_data = None
    platform_id = get_platform_id('slack')
    with db_ops(model_names=['SlackUser']) as (db, SlackUser):
        if platform_id:
            user_data = SlackUser.query.filter_by(id=user_id)  \
                .filter_by(platform_id=platform_id) \
                .first()

    if user_data:
        user_name = user_data.name
        user_email = user_data.profile_email
        # user_name = user_data.get('name')
        # user_email = user_data.get('profile_email')

    # old
    # get channel name
    # channel_data = slack_conversations.get(channel_id)
    channel_data = None
    with db_ops(model_names=['SlackChannel']) as (db, SlackChannel):
        if platform_id:
            channel_data = SlackChannel.query.filter_by(id=channel_id) \
                .filter_by(platform_id=platform_id) \
                .first()

    if channel_data:
        channel_name = channel_data.name
        channel_topic = channel_data.topic
        channel_purpose = channel_data.purpose
        channel_is_channel = channel_data.is_channel
        channel_is_group = channel_data.is_group
        channel_is_im = channel_data.is_im
        # channel_name = channel_data.get('name')
        # channel_topic = channel_data.get('topic')
        # channel_purpose = channel_data.get('purpose')
        # channel_is_channel = channel_data.get('is_channel')
        # channel_is_group = channel_data.get('is_group')
        # channel_is_im = channel_data.get('is_im')

    # convert ts into datetime formatted string
    date_string = ts_to_formatted_date(ts)

    # encapsulate all mentions to real names by id
    text = encapsulate_names_by_ids(text)

    result = 'Slack message:'
    result += ' with text \'%s\' ' % text
    if user_data and user_name:
        result += ' from %s ' % user_name
    if user_data and user_email:
        result += ' with email %s ' % user_email

    # we could also tell if it from channel, group or dm
    if channel_data and channel_is_channel:
        if channel_name:
            result += ' in a channel named %s ' % channel_name
        if channel_topic:
            result += ' with a channel topic %s ' % channel_topic
        if channel_purpose:
            result += ' with a channel purpose %s ' % channel_purpose
    elif channel_data and channel_is_group:
        # could also share num of mebers
        result += ' in a group conversation '
    elif channel_data and channel_is_im:
        result += ' in a direct message conversation '

    if date_string:
        result += ' at %s ' % date_string
    return result


def row2dict(row):
    d = {}
    for column in row.__table__.columns:
        d[column.name] = str(getattr(row, column.name))

    return d

def slack_test_etl():
    app = auth_and_load_session_slack()

    with db_ops(model_names=[]) as (db,):
        time.sleep(1)
        etl_channels(app, db)
        time.sleep(1)
        etl_users(app, db)
        time.sleep(1)
        etl_messages(app, db)

    # except SlackApiError as err:
        # print(err)


#  todo handle rate limited exception
def get_slack_comms(return_list=False, session_id=None):
    platform_id = get_platform_id('slack')
    if not platform_id:
        return None
    app = auth_and_load_session_slack()
    with db_ops(model_names=[]) as (db, ):
        etl_messages(app, db, session_id=session_id)

    slack_messages = None
    with db_ops(model_names=['SlackMessage', 'SlackChannel']) as (db, SlackMessage, SlackChannel):
        slack_messages = db.session.query(SlackMessage) \
            .join(SlackChannel, SlackMessage.slack_channel_id == SlackChannel.id) \
            .filter(SlackChannel.platform_id == platform_id) \
            .filter(SlackMessage.is_unread == True) \
            .filter(SlackMessage.session_id == session_id) \
            .all()

    if not slack_messages and return_list:
        return slack_messages

    if slack_messages:
        with db_ops(model_names=['PriorityList', 'PriorityListMethod', 'PriorityMessage' \
            , 'PriorityItem', 'PriorityItemMethod', 'SlackMessage']) as (db, PriorityList, PriorityListMethod \
            , PriorityMessage, PriorityItem, PriorityItemMethod, SlackMessage):
            plist_id = create_priority_list(db, PriorityList, PriorityListMethod, platform_id, session_id)
            # this should go to add_auth_method_now
            update_priority_list_methods(db, PriorityListMethod, platform_id, plist_id)
            # but should probably be replaced with update_p_m_a calls
            columns_list = ['ts', 'slack_channel_id', 'slack_user_id']
            fill_priority_list(db, slack_messages, get_abstract_for_slack, plist_id, PriorityMessage, PriorityList, \
                PriorityItem, PriorityItemMethod, PriorityListMethod, SlackMessage, columns_list)

    if return_list:
        return slack_messages

    result = ''
    for message in slack_messages:
        formatted_message = format_slack_message(message)
        result += '%s\n' % formatted_message

    return result



def clear_slack_tables():
    with db_ops(model_names=['SlackMessage', 'SlackAttachment', 'SlackUser', 'SlackChannel']) as \
        (db, SlackMessage, SlackAttachment, SlackUser, SlackChannel):

        for m in SlackAttachment.query.all():
            db.session.delete(m)

        for m in SlackMessage.query.all():
            db.session.delete(m)

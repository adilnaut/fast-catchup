import os
from datetime import datetime, timedelta
from dateutil import parser
import pytz
import time


from slack_bolt import App

from quickstart.connection import db_ops


def etl_messages(app, days_ago=1, max_pages=1,  verbose=False):
    # don't overwhelm API rate
    slack_channels = None

    with db_ops(model_names=['SlackChannel']) as (db, SlackChannel):
        slack_channels = SlackChannel.query.all()

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
                    with db_ops(model_names=['SlackMessage']) as (db, SlackMessage):
                        is_message = SlackMessage.query.filter_by(ts=ts).first()
                        if not is_message:
                            slack_message_kwargs = {'ts': ts
                                , 'type': type
                                , 'slack_user_id': user
                                , 'text': text
                                , 'slack_channel_id': channel_id
                                , 'is_unread': True
                                }
                            s_message = SlackMessage(**slack_message_kwargs)
                            db.session.add(s_message)
            if not has_more:
                break;


def ts_to_formatted_date(ts):
    # dangerous timstamp handling
    return datetime.fromtimestamp(int(ts.split('.')[0])).strftime('%c')


def auth_and_load_session_slack():
    app = App(
        token=os.environ.get("SLACK_BOT_TOKEN"),
        signing_secret=os.environ.get("SLACK_SIGNING_SECRET")
    )
    return app


# Opportunity(to learn): make it sqllite defined function?
def encapsulate_names_by_ids(text):
    if '<@' in text.split('>')[0]:
        left = text.split('>')[0]
        middle = left.split('<@')[1]
        user_data = None
        with db_ops(model_names=['SlackUser']) as (db, SlackUser):
            user_data = SlackUser.query.filter_by(id=middle).first()
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
    with db_ops(model_names=['SlackUser']) as (db, SlackUser):
        user_data = SlackUser.query.filter_by(id=user_id).first()

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
        channel_data = SlackChannel.query.filter_by(id=channel_id).first()

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

#  todo handle rate limited exception
def get_slack_comms(use_last_cached_emails=True, return_list=False):
    if not use_last_cached_emails:
        app = auth_and_load_session_slack()
        etl_messages(app)

    slack_messages = None
    with db_ops(model_names=['SlackMessage']) as (db, SlackMessage):
        slack_messages = SlackMessage.query.filter_by(is_unread=True).all()


    if return_list:
        return slack_messages

    result = ''
    for message in slack_messages:
        formatted_message = format_slack_message(message)
        result += '%s\n' % formatted_message

    return result

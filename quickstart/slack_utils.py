import os
from datetime import datetime, timedelta
from dateutil import parser
import pytz

from slack_bolt import App


# from pathlib import Path
#
# import sys
# sys.path.append(str(Path(sys.path[0]).parent))

from quickstart.connection import db_ops

def save_dict(in_dict, name, overwrite=False):
    # todo implement right behavior for overwrite=False
    with open('quickstart/database/%s' % name, 'w') as f:
        json.dump(in_dict, f)

def load_dict(name):
    with open('quickstart/database/%s' % name, 'r') as f:
        return json.load(f)

def enrich_channel_list(app):
    # save all conversations
    slack_conversations = {}
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
            slack_conversations[id] = {'name':name
                            , 'is_channel':is_channel
                            , 'is_group':is_group
                            , 'is_im':is_im
                            , 'created':created
                            , 'creator':creator
                            , 'is_archived':is_archived
                            , 'is_general':is_general
                            , 'unlinked':unlinked
                            , 'name_normalized':name_normalized
                            , 'is_shared':is_shared
                            , 'is_ext_shared':is_ext_shared
                            , 'is_org_shared':is_org_shared
                            , 'is_pending_ext_shared':is_pending_ext_shared
                            , 'is_member':is_member
                            , 'is_private':is_private
                            , 'is_mipm':is_mipm
                            , 'topic':topic
                            , 'purpose':purpose
                            , 'num_members':num_members}
    return slack_conversations

def enrich_user_list(app):
    response = app.client.users_list()
    status = response.get('ok')
    members = response.get('members')
    slack_users = {}
    # don't overwhelm API rate
    time.sleep(1)

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
            slack_users[id] = {'name':name
                , 'team_id':team_id
                , 'deleted':deleted
                , 'color':color
                , 'real_name':real_name
                , 'tz':tz
                , 'tz_label':tz_label
                , 'tz_offset':tz_offset
                , 'profile_avatar_hash':profile_avatar_hash
                , 'profile_status_text':profile_status_text
                , 'profile_status_emoji':profile_status_emoji
                , 'profile_real_name':profile_real_name
                , 'profile_display_name':profile_display_name
                , 'profile_real_name_normalized':profile_real_name_normalized
                , 'profile_display_name_normalized':profile_display_name_normalized
                , 'profile_email':profile_email
                , 'profile_image_24':profile_image_24
                , 'profile_image_32':profile_image_32
                , 'profile_image_48':profile_image_48
                , 'profile_image_72':profile_image_72
                , 'profile_image_192':profile_image_192
                , 'profile_image_512':profile_image_512
                , 'profile_team':profile_team
                , 'is_admin':is_admin
                , 'is_owner':is_owner
                , 'is_primary_owner':is_primary_owner
                , 'is_restricted':is_restricted
                , 'is_ultra_restricted':is_ultra_restricted
                , 'is_bot':is_bot
                , 'updated':updated
                , 'is_app_user':is_app_user
                , 'has_2fa':has_2fa
            }
    return slack_users

def enrich_message_list(app, slack_conversations, verbose=False):
    # don't overwhelm API rate
    time.sleep(1)
    channel_ids = slack_conversations.keys()
    yesterday = datetime.utcnow() - timedelta(days=1)
    unix_time = time.mktime(yesterday.timetuple())
    slack_messages = {}

    for channel_id in channel_ids:
        next_cursor = None
        for i in range(1):
            # don't overwhelm API rate
            time.sleep(0.2)
            if verbose:
                print("channel %s, id %s, request number %s" % (slack_conversations[channel_id]['name'],
                    channel_id, i))
            if next_cursor:
                response = app.client.conversations_history(channel=channel_id, oldest=unix_time,
                    limit=100, cursor=next_cursor)
            else:
                response = app.client.conversations_history(channel=channel_id,
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
                    ts = message.get('ts')
                    slack_messages[ts] = {'type':type
                        , 'user':user
                        , 'text':text
                        , 'channel':channel_id
                        }
            if not has_more:
                break;
    print_repl = False
    if print_repl and verbose:
        for ts, sm in slack_messages.items():
            print(sm)
            inp = input("Continue?Y/N\n")
            if inp == "Y":
                continue
            else:
                break
    return slack_messages


def ts_to_formatted_date(ts):
    # dangerous timstamp handling
    return datetime.fromtimestamp(int(ts.split('.')[0])).strftime('%c')


def encapsulate_names_by_ids(text, slack_users):
    if '<@' in text.split('>')[0]:
        left = text.split('>')[0]
        middle = left.split('<@')[1]
        if middle in slack_users:
            user_data = slack_users.get(middle)
            user_name = user_data.get('name')
            text = text.replace('<@%s>' % middle, user_name)
    return text


# example of slack_message
# ts: {'type': 'message', 'user': 'U04KSMCEK46', 'text': '<@U04KSMCEK46> has joined the channel', 'channel': 'C04KZ5R3CUB'}
# also available slack_conversations,
#  tasks
	# [*] add channel name in formatting messages (adilet wrote blah blah in channel x)
	# [ ] encapsulate all mentions to real names by id (use slack_users)
    # [ ] include more metadata like time, or messages being in one thread
def format_slack_message(slack_message, slack_users, slack_conversations, ts):
    text = slack_message.get('text')
    user_id = slack_message.get('user')
    channel_id = slack_message.get('channel')
    # get user name
    user_data = slack_users.get(user_id)
    if user_data:
        user_name = user_data.get('name')
        user_email = user_data.get('profile_email')
    # get channel name
    channel_data = slack_conversations.get(channel_id)
    if channel_data:
        channel_name = channel_data.get('name')
        channel_topic = channel_data.get('topic')
        channel_purpose = channel_data.get('purpose')
        channel_is_channel = channel_data.get('is_channel')
        channel_is_group = channel_data.get('is_group')
        channel_is_im = channel_data.get('is_im')

    # convert ts into datetime formatted string
    date_string = ts_to_formatted_date(ts)

    # encapsulate all mentions to real names by id
    text = encapsulate_names_by_ids(text, slack_users)

    result = 'Slack message:'
    result += ' with text \'%s\' ' % text
    if user_name:
        result += ' from %s ' % user_name
    if user_email:
        result += ' with email %s ' % user_email

    # we could also tell if it from channel, group or dm
    if channel_is_channel:
        if channel_name:
            result += ' in a channel named %s ' % channel_name
        if channel_topic:
            result += ' with a channel topic %s ' % channel_topic
        if channel_purpose:
            result += ' with a channel purpose %s ' % channel_purpose
    elif channel_is_group:
        # could also share num of mebers
        result += ' in a group conversation '
    elif channel_is_im:
        result += ' in a direct message conversation '

    if date_string:
        result += ' at %s ' % date_string
    return result


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
#  returns list
def get_slack_comms(return_list=False):

    app = auth_and_load_session_slack()

    slack_messages = None
    with db_ops(model_names=['SlackMessage']) as (db, SlackMessage):
        slack_messages = SlackMessage.query.filter_by(is_unread=True).all()

    # new_list = []
    # for m in slack_messages:
        # print(m.text)
        # new_list.append(row2dict(m))
    if return_list:

        # test if that works out of box
        return slack_messages
        # return new_list

    result = ''
    # print(new_list)
    # now return text string with all formatted messages
    # for message in new_list:
    for message in slack_messages:
        formatted_message = format_slack_message(message)
        result += '%s\n' % formatted_message

    return result


#  todo handle rate limited exception
def get_slack_comms(use_last_cached_messages=True, return_dict=False):

    slack_conversations = {}
    slack_users = {}
    slack_messages = {}
    # in the future that should depend on whether list have changed
    update_slack_data = False

    app = auth_and_load_session_slack()

    if update_slack_data:
        # save all conversations
        # enriches slack_conversations
        slack_conversations = enrich_channel_list(app)
        save_dict(slack_conversations, 'slack_conversations')

        # save all users except bots
        # enriches slack_users
        slack_users = enrich_user_list(app)
        save_dict(slack_users, 'slack_users')
    else:
        # load from disk to memory
        slack_conversations = load_dict('slack_conversations')
        slack_users = load_dict('slack_users')

    if use_last_cached_messages:
        slack_messages = load_dict('last_slack_messages')
    else:
        # save all messages for last 24 hours
        slack_messages = enrich_message_list(app, slack_conversations)
        save_dict(slack_messages, 'last_slack_messages', overwrite=True)

    if return_dict:
        return slack_messages

    result = ''
    # now return text string with all formatted messages
    for ts, message in slack_messages.items():
        formatted_message = format_slack_message(message, slack_users, slack_conversations, ts)
        result += '%s\n' % formatted_message

    write_to_file = False
    if write_to_file:
        with open('quickstart/slack_sample.txt', 'w') as f:
            f.write(result)
    return result

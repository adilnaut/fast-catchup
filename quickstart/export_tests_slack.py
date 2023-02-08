import os
import json
from datetime import datetime, timedelta
from dateutil import parser
import pytz
import time


from slack_bolt import App


def etl_messages(app, days_ago=1, max_pages=1,  verbose=False):
    # don't overwhelm API rate

    yesterday = datetime.utcnow() - timedelta(days=days_ago)
    unix_time = time.mktime(yesterday.timetuple())

    response = app.client.conversations_list(types='public_channel,private_channel,im, mpim')
    status = response.get('ok')
    slack_channels = response.get('channels')

    smessages = []

    for channel in slack_channels:
        next_cursor = None
        for i in range(max_pages):
            # don't overwhelm API rate
            time.sleep(0.2)
            if verbose:
                print("channel %s, id %s, request number %s" % (channel.get('name'),
                    channel.get('id'), i))
            if next_cursor:
                response = app.client.conversations_history(channel=channel.get('id'), oldest=unix_time,
                    limit=100, cursor=next_cursor)
            else:
                response = app.client.conversations_history(channel=channel.get('id'),
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
                    smessages.append(message)
            if not has_more:
                break;
    return smessages


def auth_and_load_session_slack():
    app = App(
        token=os.environ.get("SLACK_BOT_TOKEN"),
        signing_secret=os.environ.get("SLACK_SIGNING_SECRET")
    )
    return app



def write_tests(foldername='random'):
    app = auth_and_load_session_slack()
    slack_messages = etl_messages(app, verbose=True)
    i = 0
    folderpath = 'quickstart/tests/slack/%s' % foldername
    if not os.path.exists(folderpath):
        os.mkdir(folderpath)
    for smessage in slack_messages:
        with open('quickstart/tests/slack/%s/slack-test-%s' % (foldername, i), 'w', encoding="utf-8") as f:
            # f.write(smessage)
            json.dump(smessage, f, indent=4)
        i += 1

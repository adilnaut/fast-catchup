from __future__ import print_function

import os.path
import base64

import os
import json
import openai
import time

from slack_bolt import App

import azure.cognitiveservices.speech as speechsdk

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from urllib.request import urlopen
from datetime import datetime, timedelta
from dateutil import parser
import pytz


# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']


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

def save_dict(in_dict, name, overwrite=False):
    # todo implement right behavior for overwrite=False
    with open('quickstart/database/%s' % name, 'w') as f:
        json.dump(in_dict, f)

def load_dict(name):
    with open('quickstart/database/%s' % name, 'r') as f:
        return json.load(f)


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


def extract_messages_from_gmail_service(service):

    gmail_messages = {}

    results = service.users().messages().list(userId='me', labelIds='INBOX').execute()
    messages = results.get('messages', [])
    m_data = []

    if not messages:
        return None
    for message in messages[:20]:
        m_data.append(message['id']) # id, threadId

    for id in m_data:
        email_body = service.users().messages().get(userId='me', id=id, format='full').execute()
        if not email_body:
            continue
        snippet = email_body.get('snippet', '')
        sizeEstimate = email_body.get('sizeEstimate', '')
        labels = email_body.get('labelIds', [])
        if "UNREAD" not in labels:
            continue

        payload = email_body.get('payload')
        if not payload:
            continue
        mimeType = payload.get('mimeType', '')

        body = payload.get('body')
        if not body:
            continue
        data = body.get('data')
        if data:
            text =  base64.urlsafe_b64decode(data).decode()

        show_parts = False
        if show_parts:
            parts = payload.get('parts', [])
            i = 0
            for part in parts:
                body = part.get('body')
                if not body:
                    continue
                data = body.get('data')
                if not data:
                    continue
                text =  base64.urlsafe_b64decode(data).decode()
                i += 1


        # we will also need subject header
        show_headers = True

        if show_headers:
            headers_dict = {}
            headers = payload.get('headers')
            if headers:
                for header in headers:
                    name = header.get('name', '')
                    value = header.get('value', '')
                    if name and value:
                        headers_dict[name] = value
            else:
                pass
            date_string = headers_dict["Date"]
            if is_day_old(date_string):
                gmail_messages[id] = {'from': headers_dict["From"],
                    'snippet':snippet,
                    'subject':headers_dict["Subject"],
                    'date':date_string}

        show_raw = False
        if show_raw:
            raw = email_body.get('raw')
            if raw:
                text = base64.urlsafe_b64decode(raw).decode('ascii')

    return gmail_messages

def auth_and_load_session_gmail():
    """Shows basic usage of the Gmail API.
    Lists the user's Gmail labels.
    """
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('quickstart/token.json'):
        creds = Credentials.from_authorized_user_file('quickstart/token.json', SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'quickstart/credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('quickstart/token.json', 'w') as token:
            token.write(creds.to_json())

    try:
        # Call the Gmail API
        service = build('gmail', 'v1', credentials=creds)
        return service

    except HttpError as error:
        # TODO(developer) - Handle errors from gmail API.
        pass
        # print(f'An error occurred: {error}')

def dumps_emails(gmail_messages):
    result_text = ""

    for k,v in gmail_messages.items():
        from_item = v.get('from')
        snippet_item = v.get('snippet')
        subject_item = v.get('subject')
        date_item = v.get('date')
        result_text += "%s emailed you %s with subject %s on %s\n" % (from_item, snippet_item, subject_item, date_item)

    return result_text


def get_gmail_comms(use_last_cached_emails=True, return_dict=False):
    if use_last_cached_emails:
        gmail_messages = load_dict('last_gmail_messages')
    else:
        service = auth_and_load_session_gmail()
        gmail_messages = extract_messages_from_gmail_service(service)
        save_dict(gmail_messages, 'last_gmail_messages')
    if return_dict:
        return gmail_messages
    result_text = dumps_emails(gmail_messages)
    return result_text

def convert_to_utc(date_string):
    dt = parser.parse(date_string)
    dt = dt.astimezone(pytz.UTC)
    return dt

def is_day_old(date_string):
    date_object = convert_to_utc(date_string)
    now = datetime.now(pytz.UTC)
    return (now - date_object) < timedelta(days=1)

# depreciated
def get_unread_slack():
    with open('../unread_slack.txt', 'r') as f:
        lines = f.read()
        return lines

# todo handle API exceptions and bad results
def get_gpt_summary(prompt, unread_emails, unread_slack, verbose=False):
    openai.api_key = os.getenv("OPEN_AI_KEY")

    prompt += unread_emails
    prompt += unread_slack

    response = openai.Completion.create(
            model="text-davinci-003",
            prompt=prompt,
            temperature=0.3,
            max_tokens=150,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0
            )
    if verbose:
        print(response)
    text_response = response['choices'][0]['text']
    return text_response

# generates file.wav
# todo:
#   generate audio with random name
#   return audio filepath/random name
def generate_voice_file(text_response, verbose=False):

    # Creates an instance of a speech config with specified subscription key and service region.
    # Replace with your own subscription key and service region (e.g., "westus
    speech_key, service_region = os.getenv("SPEECH_KEY"), os.getenv("SPEECH_REGION")
    speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=service_region)

    # Set the voice name, refer to https://aka.ms/speech/voices/neural for full list.
    #speech_config.speech_synthesis_voice_name = "en-US-AriaNeural"
    # Set either the `SpeechSynthesisVoiceName` or `SpeechSynthesisLanguage`.
    speech_config.speech_synthesis_language = "en-US"
    speech_config.speech_synthesis_voice_name = "en-US-JennyNeural"
    # speech_config.speech_synthesis_voice_name = "en-US-AIGenerate2Neural"

    filepath = './app/audio/file.wav'
    audio_config = speechsdk.audio.AudioOutputConfig(filename=filepath)
    # audio_config = speechsdk.audio.AudioOutputConfig(use_default_speaker=True)
    # Receives a text from console input.

    # Creates a speech synthesizer using the default speaker as audio output.
    speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)

    # Synthesizes the received text to speech.
    # The synthesized speech is expected to be heard on the speaker with this line executed.
    result = speech_synthesizer.speak_text_async(text_response).get()

    # Checks result.
    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        if verbose:
            print("Speech synthesized to speaker for text [{}]".format(text_response))
    elif result.reason == speechsdk.ResultReason.Canceled:
        cancellation_details = result.cancellation_details
        if verbose:
            print("Speech synthesis canceled: {}".format(cancellation_details.reason))
        if cancellation_details.reason == speechsdk.CancellationReason.Error:
            if cancellation_details.error_details:
                if verbose:
                    print("Error details: {}".format(cancellation_details.error_details))
        if verbose:
            print("Did you update the subscription info?")
    return filepath

def generate_summary(prompt=None, cache_slack=False, cache_gmail=False):
    if not prompt:
        prompt = '''I\'ve got the following slack messages and emails today please give me a quick summary
            of only important messages with urgent matters first.:'''

    unread_emails = get_gmail_comms(use_last_cached_emails=cache_gmail)

    # this is from conversations.history
    unread_slack = get_slack_comms(use_last_cached_messages=cache_slack)

    gpt_summary = get_gpt_summary(prompt, unread_emails, unread_slack)

    filepath = generate_voice_file(gpt_summary)

    return prompt, gpt_summary, filepath

if __name__ == '__main__':
    app = App(
        token=os.environ.get("SLACK_BOT_TOKEN"),
        signing_secret=os.environ.get("SLACK_SIGNING_SECRET")
    )

    unread_emails = get_unread_messages()

    # this is from conversations.history
    unread_slack = get_slack_comms(app)

    # this is for real-time slack events accumulator
    # unread_slack = get_unread_slack(app)
    prompt = '''I\'ve got the following slack messages and emails today please give me a quick summary
        of only important messages with urgent matters first.:'''
    gpt_summary = get_gpt_summary(prompt, unread_emails, unread_slack)

    generate_voice_file(gpt_summary)

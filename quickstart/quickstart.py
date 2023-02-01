from __future__ import print_function

import os.path
import base64

import os
import json
import openai
import time


from openai.error import RateLimitError

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

from quickstart.slack_utils import get_slack_comms


# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']



def save_dict(in_dict, name, overwrite=False):
    # todo implement right behavior for overwrite=False
    with open('quickstart/database/%s' % name, 'w') as f:
        json.dump(in_dict, f)

def load_dict(name):
    with open('quickstart/database/%s' % name, 'r') as f:
        return json.load(f)


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


# todo handle API exceptions and bad results
def get_gpt_summary(prompt, unread_emails, unread_slack, verbose=False):
    openai.api_key = os.getenv("OPEN_AI_KEY")

    prompt += unread_emails
    prompt += unread_slack

    try:
        response = openai.Completion.create(
                model="text-davinci-003",
                prompt=prompt,
                temperature=0.3,
                max_tokens=150,
                top_p=1,
                frequency_penalty=0,
                presence_penalty=0
                )
    except RateLimitError:
        return "You exceeded your current quota, please check your plan and billing details."
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

    # from db
    unread_slack = get_slack_comms()

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
    # unread_slack = get_slack_comms(app)
    unread_slack = get_slack_comms(app)

    # this is for real-time slack events accumulator
    # unread_slack = get_unread_slack(app)
    prompt = '''I\'ve got the following slack messages and emails today please give me a quick summary
        of only important messages with urgent matters first.:'''
    gpt_summary = get_gpt_summary(prompt, unread_emails, unread_slack)

    generate_voice_file(gpt_summary)

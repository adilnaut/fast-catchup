from urllib.request import urlopen
from datetime import datetime, timedelta
from dateutil import parser
import pytz
import os
import base64

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from quickstart.connection import db_ops
# from connection import db_ops

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

# todo parse with regex
def get_guser_email(from_string):
    return from_string.split(' ')[-1].replace('<', '').replace('>', '')
def get_guser_name(from_string):
    return from_string.replace(get_guser_email(from_string), '')

# todo parse with regex
def get_is_multipart(content_type):
    return 'multipart' in content_type

def get_initial_tags(from_string):
    tags = set()

    key_list = []
    key_list.append(('newsletter', ['substack', 'morningbrew', 'ad-newsletter@a16z.com']))
    key_list.append(('alert', ['gitlab', 'linkedin', 'slack']))
    key_list.append(('social', ['meetup', 'twitter', 'facebook', 'instagram']))

    for tag, klist in key_list:
        for kword in klist:
            if kword in from_string:
                tags.add(tag)

    return list(tags)

def etl_gmail(service, unread_only=True):

    results = service.users().messages().list(userId='me', labelIds='INBOX').execute()
    messages = results.get('messages', [])
    m_data = []

    if not messages:
        return None
    for message in messages[:20]:
        id = message.get('id')
        thread_id = message.get('thread_id')
        # m_data.append(message['id']) # id, threadId
        m_data.append(id)
    with db_ops(model_names=['GmailMessage', 'GmailMessageText', \
        'GmailMessageLabel', 'GmailMessageListMetadata', \
        'GmailMessageTag', 'GmailUser']) \
        as (db, GmailMessage, GmailMessageText, \
            GmailMessageLabel, GmailMessageListMetadata, \
            GmailMessageTag, GmailUser):
        for id in m_data:
            email_body = service.users().messages().get(userId='me', id=id, format='full').execute()
            if not email_body:
                continue
            snippet = email_body.get('snippet', '')
            size_estimate = email_body.get('sizeEstimate', '')
            label_ids = email_body.get('labelIds', [])
            internal_date = email_body.get('internalDate', '')

            if unread_only:
                if "UNREAD" not in label_ids:
                    continue

            payload = email_body.get('payload')
            if not payload:
                continue
            mime_type = payload.get('mimeType', '')
            # content_type = payload.get('contentType', '')
            part_id  = payload.get('partId', '')
            filename = payload.get('filename', '')

            body = payload.get('body')
            if not body:
                continue
            data = body.get('data')
            primary_text = None
            if data:
                primary_text =  base64.urlsafe_b64decode(data).decode()

            show_parts = True
            num_parts = 0
            multiparts = []
            if show_parts:
                parts = payload.get('parts', [])
                for part in parts:
                    body = part.get('body')
                    if not body:
                        continue
                    data = body.get('data')
                    if not data:
                        continue
                    text =  base64.urlsafe_b64decode(data).decode()
                    multiparts.append(text)
                    num_parts += 1


            # we will also need subject header
            show_headers = True

            headers_dict = {}
            if show_headers:
                headers = payload.get('headers')
                if headers:
                    for header in headers:
                        name = header.get('name', '')
                        value = header.get('value', '')
                        if name and value:
                            headers_dict[name] = value


            h_mime_version = headers_dict.get('Mime-Version')
            h_content_type = headers_dict.get('Content-Type')

            date_string = headers_dict.get('Date')
            from_string = headers_dict.get('From')
            gmail_user_email = get_guser_email(from_string)
            subject = headers_dict.get('Subject')
            is_multipart = get_is_multipart(h_content_type)

            list_id = headers_dict.get('List-Id')
            message_id = headers_dict.get('Message-Id')
            list_unsubscribe = headers_dict.get('List-Unsubscribe')
            list_url = headers_dict.get('List-Url')

            tags = get_initial_tags(from_string)
            gmail_user_name = get_guser_name(from_string)


            # better attempt to insert and on conflict do nothing
            in_user = GmailUser.query.filter_by(email=gmail_user_email).first()
            if not in_user:
                user_kwargs = {'email': gmail_user_email
                    , 'name': gmail_user_name}
                gmail_user = GmailUser(**user_kwargs)
                db.session.add(gmail_user)

            gmail_message_kwargs = {'id': id
                , 'date': date_string
                , 'from_string': from_string
                , 'gmail_user_email': gmail_user_email
                , 'mime_type': mime_type
                , 'mime_version': h_mime_version
                , 'content_type': h_content_type
                , 'subject': subject
                , 'is_multipart': is_multipart
                , 'multipart_num': num_parts}


            gmail_message = GmailMessage(**gmail_message_kwargs)
            db.session.add(gmail_message)

            if snippet:
                text_kwargs = {'gmail_message_id': id
                    , 'text': snippet
                    , 'is_primary': False
                    , 'is_multipart': False
                    , 'is_summary': False
                    , 'is_snippet': True}
                gmail_message_text = GmailMessageText(**text_kwargs)
                db.session.add(gmail_message_text)


            if primary_text:
                text_kwargs = {'gmail_message_id': id
                    , 'text': primary_text
                    , 'is_primary': True
                    , 'is_multipart': False
                    , 'is_summary': False
                    , 'is_snippet': False}
                gmail_message_text = GmailMessageText(**text_kwargs)
                db.session.add(gmail_message_text)

            for i in range(len(multiparts)):
                text_kwargs = {'gmail_message_id': id
                    , 'text': multiparts[i]
                    , 'is_primary': False
                    , 'is_multipart': True
                    , 'is_summary': False
                    , 'is_snippet': False
                    , 'multipart_index': i}
                gmail_message_text = GmailMessageText(**text_kwargs)
                db.session.add(gmail_message_text)

            for label in label_ids:
                label_kwargs = {'gmail_message_id': id
                    , 'label': label}
                gmail_message_label = GmailMessageLabel(**label_kwargs)
                db.session.add(gmail_message_label)

            if list_id:
                list_metadata_kwargs = {'gmail_message_id': id
                    , 'list_id': list_id
                    , 'message_id': message_id
                    , 'list_unsubscribe': list_unsubscribe
                    , 'list_url': list_url}
                list_metadata = GmailMessageListMetadata(**list_metadata_kwargs)
                db.session.add(list_metadata)

            for tag in tags:
                tag_kwargs = {'gmail_message_id': id
                    , 'tag': tag}
                gmail_message_tag = GmailMessageTag(**tag_kwargs)
                db.session.add(gmail_message_tag)




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
def test_etl():
    service = auth_and_load_session_gmail()
    etl_gmail(service)

def list_gtexts():
    gmail_messages = None
    with db_ops(model_names=['GmailMessage', 'GmailMessageLabel', 'GmailMessageText']) as \
        (db, GmailMessage, GmailMessageLabel, GmailMessageText):

        gmail_messages = db.session.query(GmailMessage, GmailMessageText) \
            .join(GmailMessageLabel) \
            .join(GmailMessageText) \
            .filter(GmailMessageLabel.label == 'UNREAD').all()

    return gmail_messages

def clean_gmail_tables():
    with db_ops(model_names=['GmailMessage', 'GmailMessageText', \
        'GmailMessageLabel', 'GmailMessageListMetadata', \
        'GmailMessageTag', 'GmailUser']) \
        as (db, GmailMessage, GmailMessageText, \
        GmailMessageLabel, GmailMessageListMetadata, \
        GmailMessageTag, GmailUser):
        for m in GmailMessageLabel.query.all():
            db.session.delete(m)
        for m in GmailMessageTag.query.all():
            db.session.delete(m)
        for m in GmailMessageListMetadata.query.all():
            db.session.delete(m)
        for m in GmailMessageText.query.all():
            db.session.delete(m)
        for m in GmailMessage.query.all():
            db.session.delete(m)
        for u in GmailUser.query.all():
            db.session.delete(u)



def get_gmail_comms(use_last_cached_emails=True, return_list=False):
    if not use_last_cached_emails:
        service = auth_and_load_session_gmail()
        etl_gmail(service)

    gmail_messages = None
    with db_ops(model_names=['GmailMessage', 'GmailMessageLabel', 'GmailMessageText']) as \
        (db, GmailMessage, GmailMessageLabel, GmailMessageText):

        gmail_messages = db.session.query(GmailMessage, GmailMessageText) \
            .join(GmailMessageLabel) \
            .join(GmailMessageText) \
            .filter_by(GmailMessageLabel.label == 'UNREAD').all()



    if return_list:
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

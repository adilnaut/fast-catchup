from urllib.request import urlopen
from datetime import datetime, timedelta
from dateutil import parser
import pytz
import os
import base64
import hashlib
import tempfile
import shutil
import uuid

from collections import OrderedDict

from urlextract import URLExtract
from urllib.parse import urlparse

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.exceptions import RefreshError

from quickstart.connection import db_ops, get_current_user, get_platform_id
from quickstart.sqlite_utils import get_upsert_query, get_insert_query
from quickstart.priority_engine import create_priority_list, update_priority_list_methods, fill_priority_list
from quickstart.platform import get_abstract_for_gmail

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

# todo parse with regex
def get_guser_email(from_string):
    return from_string.split(' ')[-1].replace('<', '').replace('>', '')
def get_guser_name(from_string):
    return from_string.replace(get_guser_email(from_string), '')

def extract_links(text):
    extractor = URLExtract()
    urls = extractor.find_urls(text)
    return urls

def extract_domain(link):
    t = urlparse(link).netloc
    return '.'.join(t.split('.')[-2:])

# todo parse with regex
def get_is_multipart(content_type):
    if content_type:
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

def parse_email_part(part, id, service, db, handle_subparts=False, extract_text_from_mixed = False, verbose=False):
    part_id_0 = part.get('partId', '')
    mime_type_0 = part.get('mimeType', '')
    filename_0 = part.get('filename', '')
    headers_0 = part.get('headers', {})

    body_0 = part.get('body')

    text = None
    text_parts = []
    num_processed = 0

    # todo handle 'multipart/alternative'
    if mime_type_0 == 'multipart/alternative':
        if not handle_subparts:
            raise Exception('Only 1 step depth recursion permitted!')
        part_parts = part.get('parts', [])
        for part_1 in part_parts:
            # only go 1 way deeper
            text_parts_in, num_processed_in = parse_email_part(part_1, id, service, db)
            text_parts.extend(text_parts_in)
            num_processed += num_processed_in
    if mime_type_0 == 'text/plain':
        data_0 = body_0.get('data')
        size_0 = body_0.get('size')
        if not data_0:
            return [], 0
        text = base64.urlsafe_b64decode(data_0).decode()
    elif mime_type_0 == 'text/html':
        data_0 = body_0.get('data')
        size_0 = body_0.get('size')
        if not data_0:
            return [], 0
        if extract_text_from_mixed:
            text = base64.urlsafe_b64decode(data_0).decode()
            text = get_text_from_html(text) + '\n'

    # todo handle general attachment case
    elif 'application/' in mime_type_0:
        size_0 = body_0.get('size')
        attachment_id_0 = body_0.get('attachmentId')
        if verbose:
            print("We have a file with filename-%s" % filename_0)
        # handle attachment here:
        # messageId is id
        # attachmentID is attachment_id_0
        # userId is me

        # now get attachment from api
        file_response = service.users().messages().attachments().get(
            userId='me', messageId=id, id=attachment_id_0).execute()
        # If successful, the response body contains an instance of MessagePartBody.
        # print(file_response)
        file_data = file_response.get('data', '')
        file_size = file_response.get('size', '')

        # todo - parse more cautiously
        file_extension = mime_type_0.split('/')[1]

        if verbose:
            print('file size: %s' % file_size)
        file_attachment_id = file_response.get('attachmentId', '')
        while file_attachment_id:
            # handle more chunks of file
            raise Exception('Multiple file chunks not implemented!')
        file_content = base64.urlsafe_b64decode(file_data)

        # generate hash for filename
        file_hash = hashlib.md5(file_content).hexdigest()

        workdir_ = 'file_store'
        filepath_ = os.path.join(workdir_, '%s.%s' % (file_hash, file_extension))
        # check if hash isn't on fileserver yet
        is_file_exist = os.path.exists(filepath_)

        # if not upload to server
        if not is_file_exist:
            datafile = open(filepath_, 'wb')
            datafile.write(file_content)
            datafile.close()

        ga_kwargs = OrderedDict([('gmail_message_id', id)
            , ('md5', file_hash)
            , ('attachment_id', attachment_id_0)
            , ('file_size', size_0)
            , ('original_filename', filename_0)
            , ('part_id', part_id_0)
            , ('mime_type', mime_type_0)
            , ('file_extension', file_extension)
            , ('filepath', filepath_)])
        ga_query = get_upsert_query('gmail_attachment', ga_kwargs.keys(), 'gmail_message_id, md5')
        db.session.execute(ga_query, ga_kwargs)
    else:
        if verbose:
            print('This type of content %s is not supported yet' % mime_type_0)
    if text:
        text_parts.append(text)
        num_processed += 1
        links = extract_links(text)
        for link_ in links:
            link_kwargs = OrderedDict([('gmail_message_id', id)
                , ('link', link_)
                , ('domain', extract_domain(link_))])
            link_query = get_upsert_query('gmail_link', link_kwargs.keys(), 'gmail_message_id, link')
            db.session.execute(link_query, link_kwargs)
    return text_parts, num_processed


def etl_gmail(service, db, session_id=None, max_messages=5, unread_only=True):

    results = service.users().messages().list(userId='me', labelIds='INBOX').execute()
    messages = results.get('messages', [])
    m_data = []

    if not messages:
        return None
    for message in messages[:max_messages]:
        id = message.get('id')
        thread_id = message.get('thread_id')
        # m_data.append(message['id']) # id, threadId
        m_data.append(id)


    for id in m_data:
        # todo:
        #  1. check if email id is not present
        #  2. if present, skip
        with db_ops(model_names=['GmailMessage']) as (db_s, GmailMessage):
            gid = GmailMessage.query.filter_by(id=id).first()
            if gid:
                continue
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

                extract_text_from_mixed = False
                handle_subparts = True

                multiparts_in, num_processed_in = parse_email_part(part, id, service, db,
                    handle_subparts=handle_subparts, extract_text_from_mixed=extract_text_from_mixed)
                multiparts.extend(multiparts_in)
                num_parts += num_processed_in

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

        in_user = None
        platform_id = get_platform_id('gmail')
        user_kwargs = OrderedDict([('email', gmail_user_email)
            , ('platform_id', platform_id)
            , ('name', gmail_user_name)])
        user_query = get_upsert_query('gmail_user', user_kwargs.keys(), 'email, platform_id')
        db.session.execute(user_query, user_kwargs)

        gm_kwargs = OrderedDict([('id', id)
            , ('date', date_string)
            , ('from_string', from_string)
            , ('gmail_user_email', gmail_user_email)
            , ('mime_type', mime_type)
            , ('mime_version', h_mime_version)
            , ('content_type', h_content_type)
            , ('subject', subject)
            , ('is_multipart', is_multipart)
            , ('session_id', session_id)
            , ('multipart_num', num_parts)])
        gm_query = get_upsert_query('gmail_message', gm_kwargs.keys(), 'id')
        db.session.execute(gm_query, gm_kwargs)

        if snippet:
            text_hash = hashlib.md5(snippet.encode('utf-8')).hexdigest()
            text_kwargs = OrderedDict([('gmail_message_id', id)
                , ('text_hash', text_hash)
                , ('text', snippet)
                , ('is_primary', False)
                , ('is_multipart', False)
                , ('is_summary', False)
                , ('is_snippet', True)])
            text_query = get_upsert_query('gmail_message_text', text_kwargs.keys(), 'gmail_message_id, text_hash')
            db.session.execute(text_query, text_kwargs)

        if primary_text:
            text_hash = hashlib.md5(primary_text.encode('utf-8')).hexdigest()
            text_kwargs = OrderedDict([('gmail_message_id', id)
                , ('text_hash', text_hash)
                , ('text', primary_text)
                , ('is_primary', True)
                , ('is_multipart', False)
                , ('is_summary', False)
                , ('is_snippet', False)])
            text_query = get_upsert_query('gmail_message_text', text_kwargs.keys(), 'gmail_message_id, text_hash')
            db.session.execute(text_query, text_kwargs)

        for i in range(len(multiparts)):
            text_hash = hashlib.md5(multiparts[i].encode('utf-8')).hexdigest()
            text_kwargs = OrderedDict([('gmail_message_id', id)
                , ('text_hash', text_hash)
                , ('text', multiparts[i])
                , ('is_primary', False)
                , ('is_multipart', True)
                , ('is_summary', False)
                , ('is_snippet', False)
                , ('multipart_index', i)])
            text_query = get_upsert_query('gmail_message_text', text_kwargs.keys(), 'gmail_message_id, text_hash')
            db.session.execute(text_query, text_kwargs)

        for label in label_ids:
            label_kwargs = OrderedDict([('gmail_message_id', id)
                , ('label', label)])
            label_query = get_insert_query('gmail_message_label', label_kwargs.keys())
            db.session.execute(label_query, label_kwargs)

        if list_id:
            list_metadata_kwargs = OrderedDict([('gmail_message_id', id)
                , ('list_id', list_id)
                , ('message_id', message_id)
                , ('list_unsubscribe', list_unsubscribe)
                , ('list_url', list_url)])
            meta_query = get_insert_query('gmail_message_list_metadata', list_metadata_kwargs.keys())
            db.session.execute(meta_query, list_metadata_kwargs)

        for tag in tags:
            tag_kwargs = OrderedDict([('gmail_message_id', id)
                , ('tag', tag)])
            tag_query = get_insert_query('gmail_message_tag', tag_kwargs.keys())
            db.session.execute(tag_query, tag_kwargs)




#  todo handle cases:
#  when  tokens don't exist in database
#  when cred don't exist in database
#  when shutil couldn't find or copy file
def auth_and_load_session_gmail():
    """Shows basic usage of the Gmail API.
    Lists the user's Gmail labels.
    """

    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.

    # the task is to fetch 2 auth data files
    # that would have data in file_store
    # and move them to temp folder and give unique name
    # and after both tokenpath and credpath would be assigned
    # accessible filepaths on the local store - script should work

    platform_id = get_platform_id('gmail')
    tokenpath = None
    credpath = None

    with db_ops(model_names=['AuthData']) as (db, AuthData):
        token_row = AuthData.query \
            .filter_by(platform_id=platform_id) \
            .filter_by(name='token.json') \
            .filter_by(is_path=True) \
            .first()
        # print(token_row)
        cred_row = AuthData.query \
            .filter_by(platform_id=platform_id) \
            .filter_by(name='credentials.json') \
            .filter_by(is_path=True) \
            .first()
        # print(cred_row)
        tempdir = tempfile.gettempdir()

        if token_row:
            tokenpath = os.path.join(tempdir, token_row.name)
            shutil.copyfile(token_row.file_path, tokenpath)
            # print('shutil')
        # else:
        #     tokenpath = os.path.join(tempdir, 'token.json')
        #     print('ne shutil')
        if cred_row:
            credpath = os.path.join(tempdir, cred_row.name)
            shutil.copyfile(cred_row.file_path, credpath)

    if tokenpath and os.path.exists(tokenpath):
        creds = Credentials.from_authorized_user_file(tokenpath, SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError as error:
                print("Caught Refresh token error")
                # os.remove('quickstart/token.json')
                exit()
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                credpath, SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        if tokenpath and os.path.exists(tokenpath):
            os.remove(tokenpath)
        filename = '%s-%s' % (uuid.uuid4().hex, 'token.json')
        new_tokenpath = os.path.join('file_store', filename)
        with open(new_tokenpath, 'w') as token:
            token.write(creds.to_json())
            authdata_kwargs = OrderedDict([('platform_id', platform_id)
                , ('name', 'token.json')
                , ('is_data', False)
                , ('is_blob', False)
                , ('is_path', True)
                , ('file_path', new_tokenpath)])
            auth_query = get_upsert_query('auth_data', authdata_kwargs.keys(), 'platform_id, name')
            db.session.execute(auth_query, authdata_kwargs)
    try:
        # Call the Gmail API
        service = build('gmail', 'v1', credentials=creds)
        return service

    except HttpError as error:
        # TODO(developer) - Handle errors from gmail API.
        pass
        # print(f'An error occurred: {error}')

def get_list_data_by_g_id(gmail_message_id):
    with db_ops(model_names=['GmailUser', 'GmailMessage', 'GmailMessageText']) as \
        (db, GmailUser, GmailMessage, GmailMessageText):
        gmail_message = GmailMessage.query.filter_by(id=gmail_message_id).first()

        id_ = gmail_message.id
        email_ = gmail_message.gmail_user_email
        name_ = None

        platform_id = get_platform_id('gmail')
        gmail_user = GmailUser.query.filter_by(email=email_) \
            .filter_by(platform_id=platform_id) \
            .one()

        name_ = gmail_user.name
        subject_ = gmail_message.subject
        date_ = gmail_message.date
        if date_:
            date_ = convert_to_utc(date_).strftime('%m/%d/%Y, %H:%M:%S')

        text_summary = GmailMessageText.query.filter_by(gmail_message_id=gmail_message_id) \
            .filter_by(is_summary=True).first()
        snippet = GmailMessageText.query.filter_by(gmail_message_id=gmail_message_id) \
            .filter_by(is_snippet=True).first()
        if text_summary:
            text_summary = text_summary.text
        elif snippet:
            text_summary = snippet.text
        else:
            text_summary = subject_

        list_body = {}
        list_body['headline'] = name_
        list_body['text'] = text_summary
        list_body['subject'] = subject_
        list_body['date'] = date_
        return list_body

def dumps_emails(gmail_messages):
    result_text = ""

    for row in gmail_messages:
        id_ = row.id
        email_ = row.gmail_user_email
        name_ = None
        snippet_ = None
        with db_ops(model_names=['GmailUser', 'GmailMessageText']) as \
            (db, GmailUser, GmailMessageText):
            platform_id = get_platform_id('gmail')
            gmail_user = GmailUser.query.filter_by(email=email_) \
                .filter_by(platform_id=platform_id) \
                .one()
            gm_snippet = GmailMessageText.query.filter_by(gmail_message_id=id_) \
                .filter_by(is_snippet=True).one()
            name_ = gmail_user.name
            snippet_ = gm_snippet.text
        subject_ = row.subject
        date_ = row.date
        if date_:
            date_ = convert_to_utc(date_).strftime('%m%d')
        result_text += "%s emailed you %s with subject %s on %s\n" % (name_, snippet_, subject_, date_)

    return result_text


def get_gmail_comms(return_list=False, session_id=None):

    platform_id = get_platform_id('gmail')
    if not platform_id:
        return None
    service = auth_and_load_session_gmail()
    with db_ops(model_names=[]) as (db, ):
        etl_gmail(service, db, session_id=session_id)


    gmail_messages = None

    with db_ops(model_names=['GmailMessage', 'GmailMessageLabel', 'GmailUser']) as \
        (db, GmailMessage, GmailMessageLabel, GmailUser):

        gmail_messages = db.session.query(GmailMessage) \
            .join(GmailMessageLabel, GmailMessageLabel.gmail_message_id == GmailMessage.id) \
            .join(GmailUser, GmailUser.email == GmailMessage.gmail_user_email) \
            .filter(GmailUser.platform_id == platform_id) \
            .filter(GmailMessageLabel.label == 'UNREAD') \
            .filter(GmailMessage.session_id == session_id) \
            .all()

    if not gmail_messages and return_list:
        return gmail_messages

    if gmail_messages:
        with db_ops(model_names=['PriorityList', 'PriorityListMethod', 'PriorityMessage' \
            , 'PriorityItem', 'PriorityItemMethod', 'GmailMessage']) as (db, PriorityList, PriorityListMethod \
            , PriorityMessage, PriorityItem, PriorityItemMethod, GmailMessage):
            plist_id = create_priority_list(db, PriorityList, PriorityListMethod, platform_id, session_id)
            # this should go to add_auth_method_now
            update_priority_list_methods(db, PriorityListMethod, platform_id, plist_id)
            # but should probably be replaced with update_p_m_a calls
            columns_list = ['id', 'GmailMessageLabel.label', 'gmail_user_email', 'content_type']
            fill_priority_list(db, gmail_messages, get_abstract_for_gmail, plist_id, PriorityMessage, PriorityList, \
                PriorityItem, PriorityItemMethod, PriorityListMethod, GmailMessage, columns_list)

    if return_list:
        return gmail_messages

    result_text = dumps_emails(gmail_messages)
    return result_text

def convert_to_utc(date_string):
    if not date_string:
        return ''
    dt = parser.parse(date_string)
    dt = dt.astimezone(pytz.UTC)
    return dt

def is_day_old(date_string):
    date_object = convert_to_utc(date_string)
    now = datetime.now(pytz.UTC)
    return (now - date_object) < timedelta(days=1)

def test_etl():
    service = auth_and_load_session_gmail()
    with db_ops(model_names=[]) as (db, ):
        etl_gmail(service, db)

def get_gmail_attribute(att_name):
    with db_ops(model_names=['GmailMessage', 'GmailMessageLabel', att_name, 'GmailUser']) as \
        (db, GmailMessage, GmailMessageLabel, AttTable, GmailUser):

        gmail_messages = db.session.query(GmailMessage, AttTable) \
            .join(GmailMessageLabel, GmailMessageLabel.gmail_message_id == GmailMessage.id) \
            .join(AttTable, AttTable.gmail_message_id == GmailMessage.id) \
            .join(GmailUser, GmailUser.email == GmailMessage.gmail_user_email) \
            .filter(GmailMessageLabel.label == 'UNREAD') \
            .filter(GmailUser.platform_id == get_platform_id('gmail')) \
            .all()

    return gmail_messages

def clean_gmail_tables():
    # todo: make table relationships explicit and cascade on delte, then delete user/platform
    with db_ops(model_names=['GmailMessage', 'GmailMessageText', \
        'GmailMessageLabel', 'GmailMessageListMetadata', \
        'GmailMessageTag', 'GmailUser', 'GmailAttachment', 'GmailLink']) \
        as (db, GmailMessage, GmailMessageText, \
        GmailMessageLabel, GmailMessageListMetadata, \
        GmailMessageTag, GmailUser, GmailAttachment, GmailLink):
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
        for m in GmailAttachment.query.all():
            db.session.delete(m)
        for m in GmailLink.query.all():
            db.session.delete(m)

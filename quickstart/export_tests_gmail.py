import base64
import json
import codecs
import hashlib
import os

from bs4 import BeautifulSoup
from urlextract import URLExtract



from quickstart.gmail_utils import auth_and_load_session_gmail, is_day_old

def get_text_from_html(html_text):

    soup = BeautifulSoup(html_text, features="html.parser")

    # kill all script and style elements
    for script in soup(["script", "style"]):
        script.extract()    # rip it out

    # get text
    text = soup.get_text()

    # break into lines and remove leading and trailing space on each
    lines = (line.strip() for line in text.splitlines())
    # break multi-headlines into a line each
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    # drop blank lines
    text = '\n'.join(chunk for chunk in chunks if chunk)
    return text



def extract_links(text):
    extractor = URLExtract()
    urls = extractor.find_urls(text)
    return urls


def extract_messages_from_gmail_service(service, num_messages=10):

    gmail_messages = []

    results = service.users().messages().list(userId='me', labelIds='INBOX').execute()
    messages = results.get('messages', [])
    m_data = []

    if not messages:
        return None
    for message in messages[:num_messages]:
        m_data.append(message['id']) # id, threadId

    for id in m_data:
        email_content = ""

        email_body = service.users().messages().get(userId='me', id=id, format='full').execute()
        if not email_body:
            continue
        snippet = email_body.get('snippet', '')
        sizeEstimate = email_body.get('sizeEstimate', '')
        labels = email_body.get('labelIds', [])

        # get rid of not UNREAD
        # if "UNREAD" not in labels:
        #     continue

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
            email_content += get_text_from_html(text) + '\n'
        show_parts = True
        links = None
        if show_parts:
            parts = payload.get('parts', [])


            i = 0
            for part in parts:
                extract_text_from_mixed = False
                handle_recursive = True
                if handle_recursive:
                    # handle recursive parts(?):
                    # parts_1 = parts.get('parts', [])
                    part_parts = part.get('parts', [])
                    for part_1 in part_parts:
                        part_id_1 = part_1.get('partId', '')
                        mime_type_1 = part_1.get('mimeType', '')
                        filename_1 = part_1.get('filename', '')
                        headers_1 = part_1.get('headers', {})
                        body_1 = part_1.get('body', {})
                        if not body_1:
                            continue
                        data_1 = body_1.get('data', '')
                        size_1 = body_1.get('size', '')
                        text = None
                        if mime_type_1 == 'text/plain':
                            text = base64.urlsafe_b64decode(data_1).decode()
                            links = extract_links(text)
                        elif mime_type_1 == 'text/html':
                            if extract_text_from_mixed:
                                text = base64.urlsafe_b64decode(data_1).decode()
                                text = get_text_from_html(text) + '\n'
                        else:
                            # todo raise exception
                            print('1 - This type of content %s is not supported yet' % mime_type_1)
                        if text:
                            email_content += text + '\n'
                    continue
                part_id_0 = part.get('partId', '')
                mime_type_0 = part.get('mimeType', '')
                filename_0 = part.get('filename', '')
                headers_0 = part.get('headers', {})

                body_0 = part.get('body')
                if not body_0:
                    continue
                text = None
                extract_text_from_mixed = False


                if mime_type_0 == 'text/plain':
                    data_0 = body_0.get('data')
                    size_0 = body_0.get('size')
                    if not data_0:
                        continue
                    text = base64.urlsafe_b64decode(data_0).decode()
                elif mime_type_0 == 'text/html':
                    data_0 = body_0.get('data')
                    size_0 = body_0.get('size')
                    if not data_0:
                        continue
                    if extract_text_from_mixed:
                        text = base64.urlsafe_b64decode(data_0).decode()
                        text = get_text_from_html(text) + '\n'
                elif mime_type_0 == 'application/pdf':
                    size_0 = body_0.get('size')
                    attachment_id_0 = body_0.get('attachmentId')

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

                    gmail_attachment_kwargs = {'md5': file_hash
                        , 'attachment_id': attachment_id_0
                        , 'file_size': size_0
                        , 'gmail_message_id': id
                        , 'original_filename': filename_0
                        , 'part_id': part_id_0
                        , 'mime_type': mime_type_0
                        , 'file_extension': file_extension
                        , 'filepath': filepath_
                    }



                # todo handle general attachment case
                elif mime_type_0 == 'application/*':
                    print("Not implemented!")
                    pass
                else:
                    print('This type of content %s is not supported yet' % mime_type_0)
                    pass

                email_content += text + '\n' if text else ''
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
            # date_string = headers_dict["Date"]
            # if is_day_old(date_string):
            #     gmail_messages[id] = {'from': headers_dict["From"],
            #         'snippet':snippet,
            #         'subject':headers_dict["Subject"],
            #         'date':date_string}
        if links:
            email_content += '\nLinks: [%s]' % ','.join(links)
        email_content += '\n%s' % json.dumps(email_body, indent=4)
        email_content += '\n%s' % json.dumps(headers_dict, indent=4)
        email_content += '\nSnippet:\n%s' % snippet
        email_content += '\nLabels:\n%s' % labels

        show_raw = False
        if show_raw:
            raw = email_body.get('raw')
            if raw:
                text = base64.urlsafe_b64decode(raw).decode()
        gmail_messages.append(email_content)

    return gmail_messages


def write_tests(foldername='random'):
    service = auth_and_load_session_gmail()
    gmail_messages = extract_messages_from_gmail_service(service)
    i = 0
    folderpath = 'quickstart/tests/%s' % foldername
    if not os.path.exists(folderpath):
        os.mkdir(folderpath)
    for gmessage in gmail_messages:
        with open('quickstart/tests/%s/gmail-test-%s' % (foldername, i), 'w', encoding="utf-8") as f:
            f.write(gmessage)
        i += 1

if __name__ == '__main__':
    service = auth_and_load_session_gmail()
    gmail_messages = extract_messages_from_gmail_service(service)
    i = 0
    for gmessage in gmail_messages:
        with open('quickstart/tests/attachment/gmail-test-%s' % i, 'w', encoding="utf-8") as f:
            f.write(gmessage)
        i += 1

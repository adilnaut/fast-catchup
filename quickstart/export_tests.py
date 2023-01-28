import base64
import json

from bs4 import BeautifulSoup

from quickstart import auth_and_load_session_gmail, is_day_old

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

# def get_text_from_html(html_text):
#
#     return html_text


def extract_messages_from_gmail_service(service):

    gmail_messages = []

    results = service.users().messages().list(userId='me', labelIds='INBOX').execute()
    messages = results.get('messages', [])
    m_data = []

    if not messages:
        return None
    for message in messages[:20]:
        m_data.append(message['id']) # id, threadId

    for id in m_data:
        email_content = ""

        email_body = service.users().messages().get(userId='me', id=id, format='full').execute()
        if not email_body:
            continue
        snippet = email_body.get('snippet', '')
        sizeEstimate = email_body.get('sizeEstimate', '')
        labels = email_body.get('labelIds', [])

        # get rid of UNREAD
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
                email_content += get_text_from_html(text) + '\n'
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

if __name__ == '__main__':
    service = auth_and_load_session_gmail()
    gmail_messages = extract_messages_from_gmail_service(service)
    i = 0
    for gmessage in gmail_messages:
        with open('quickstart/tests/souped/gmail-test-%s' % i, 'w', encoding="utf-8") as f:
            f.write(gmessage)
        i += 1

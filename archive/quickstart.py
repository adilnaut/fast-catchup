
def get_unread_messages_old():
    """Shows basic usage of the Gmail API.
    Lists the user's Gmail labels.
    """
    result_text = ''
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
                    result_text += "%s emailed you %s with subject %s \n" % (headers_dict["From"], snippet, headers_dict["Subject"])


            show_raw = False
            if show_raw:
                raw = email_body.get('raw')
                if raw:
                    text = base64.urlsafe_b64decode(raw).decode('ascii')

        return result_text

    except HttpError as error:
        # TODO(developer) - Handle errors from gmail API.
        pass
        # print(f'An error occurred: {error}')

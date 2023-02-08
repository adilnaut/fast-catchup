from app import db


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), index=True, unique=True)
    email = db.Column(db.String(120), index=True, unique=True)
    password_hash = db.Column(db.String(128))

    def __repr__(self):
        return '<user {}>'.format(self.username)

class SlackUser(db.Model):
    # id = db.Column(db.Integer, primary_key=True)
    id = db.Column(db.String(20), primary_key=True)
    name = db.Column(db.String(120), index=True)
    team_id = db.Column(db.String(20), index=True)
    deleted = db.Column(db.Boolean())
    color = db.Column(db.String(20))
    real_name = db.Column(db.String(120))
    tz = db.Column(db.String(120))
    tz_label = db.Column(db.String(120))
    tz_offset = db.Column(db.Integer())
    profile_avatar_hash = db.Column(db.String(120))
    profile_status_text = db.Column(db.String(120))
    profile_status_emoji = db.Column(db.String(120))
    profile_real_name = db.Column(db.String(120))
    profile_display_name = db.Column(db.String(120))
    profile_real_name_normalized = db.Column(db.String(120))
    profile_display_name_normalized = db.Column(db.String(120))
    profile_email = db.Column(db.String(120))
    profile_image_24 = db.Column(db.String(120))
    profile_image_32 = db.Column(db.String(120))
    profile_image_48 = db.Column(db.String(120))
    profile_image_72 = db.Column(db.String(120))
    profile_image_192 = db.Column(db.String(120))
    profile_image_512 = db.Column(db.String(120))
    profile_team = db.Column(db.String(20))
    is_admin = db.Column(db.Boolean())
    is_owner = db.Column(db.Boolean())
    is_primary_owner = db.Column(db.Boolean())
    is_restricted = db.Column(db.Boolean())
    is_ultra_restricted = db.Column(db.Boolean())
    is_bot = db.Column(db.Boolean())
    updated = db.Column(db.Integer())
    is_app_user = db.Column(db.Boolean())
    has_2fa = db.Column(db.Boolean())

    def __repr__(self):
        return '<s-user {}-{}>'.format(self.id, self.name)


class SlackChannel(db.Model):
    # id = db.Column(db.Integer, primary_key=True)
    id = db.Column(db.String(20), primary_key=True)
    name = db.Column(db.String(120), index=True)
    is_channel = db.Column(db.Boolean())
    is_group = db.Column(db.Boolean())
    is_im = db.Column(db.Boolean())
    created = db.Column(db.Integer())
    creator = db.Column(db.String(20), index=True)
    is_archived = db.Column(db.Boolean())
    is_general = db.Column(db.Boolean())
    unlinked = db.Column(db.Integer())
    name_normalized = db.Column(db.String(120))
    is_shared = db.Column(db.Boolean())
    is_ext_shared = db.Column(db.Boolean())
    is_org_shared = db.Column(db.Boolean())
    is_pending_ext_shared = db.Column(db.Boolean())
    is_member = db.Column(db.Boolean())
    is_private = db.Column(db.Boolean())
    is_mipm = db.Column(db.Boolean())
    topic = db.Column(db.Text())
    purpose = db.Column(db.Text())
    num_members = db.Column(db.Integer())

    def __repr__(self):
        return '<s-channel {}-{}>'.format(self.id, self.name)


class SlackMessage(db.Model):
    # id = db.Column(db.Integer, primary_key=True)
    ts = db.Column(db.String(40), primary_key=True)
    type = db.Column(db.String(60))
    slack_user_id = db.Column(db.String(20), db.ForeignKey('slack_user.id'))
    slack_channel_id = db.Column(db.String(20), db.ForeignKey('slack_channel.id'))
    text = db.Column(db.Text())
    is_unread = db.Column(db.Boolean())

    def __repr__(self):
        return '<s-message in {} by {} on {}>'.format(self.slack_channel_id, self.slack_user_id, self.ts)

class GmailMessageLabel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    gmail_message_id = db.Column(db.String(240), db.ForeignKey('gmail_message.id'))
    label = db.Column(db.String(240))
    def __repr__(self):
        return '<g-label {}>'.format(self.label)

class GmailMessageText(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    gmail_message_id = db.Column(db.String(240), db.ForeignKey('gmail_message.id'))
    text = db.Column(db.UnicodeText())
    is_primary = db.Column(db.Boolean())
    is_multipart = db.Column(db.Boolean())
    is_summary = db.Column(db.Boolean())
    is_snippet = db.Column(db.Boolean())
    multipart_index = db.Column(db.Integer)

    def __repr__(self):
        if bool(self.is_multipart) == True:
            return '<g-message-multipart {}>'.format(self.multipart_index)
        elif self.text:
            return '<g-message-text {}>'.format(self.text[:10].replace('\n', ''))
        else:
            return '<g-message-text {}>'.format(self.gmail_message_id)


class GmailMessageListMetadata(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    gmail_message_id = db.Column(db.String(240), db.ForeignKey('gmail_message.id'))
    # what about list/newsletter fields
    list_id = db.Column(db.Text())
    message_id = db.Column(db.Text())
    list_unsubscribe = db.Column(db.Text())
    list_url = db.Column(db.Text())

    def __repr__(self):
        return '<g-message-list mdata {}>'.format(self.list_id)


class GmailMessageTag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    gmail_message_id = db.Column(db.String(240), db.ForeignKey('gmail_message.id'))
    tag = db.Column(db.String(240))

    def __repr__(self):
        return '<g-tag {}>'.format(self.tag)

class GmailMessage(db.Model):
    id = db.Column(db.String(240), primary_key=True)
    date = db.Column(db.Text())
    from_string = db.Column(db.Text())
    gmail_user_email = db.Column(db.String(240), db.ForeignKey('gmail_user.email'))
    mime_version = db.Column(db.String(10))
    mime_type = db.Column(db.Text())
    content_type = db.Column(db.Text())
    subject = db.Column(db.Text())
    is_multipart = db.Column(db.Boolean())
    multipart_num = db.Column(db.Integer)

    def __repr__(self):
        return '<g-message by {} on {}>'.format(self.from_string, self.date)


class GmailUser(db.Model):
    email = db.Column(db.String(240), primary_key=True)
    name = db.Column(db.Text())
    is_newsletter = db.Column(db.Boolean())
    type = db.Column(db.String(120))

    def __repr__(self):
        return '<g-user{} with email {}>'.format(self.name, self.email)


class GmailAttachment(db.Model):
    md5 = db.Column(db.Text(), primary_key=True)
    gmail_message_id = db.Column(db.String(240), db.ForeignKey('gmail_message.id'), primary_key=True)
    attachment_id = db.Column(db.Text())
    file_size = db.Column(db.Integer)
    original_filename = db.Column(db.Text())
    part_id = db.Column(db.Text())
    mime_type = db.Column(db.Text())
    file_extension = db.Column(db.Text())
    filepath = db.Column(db.Text())

    def __repr__(self):
        return '<g-attachment with filename {}>'.format(self.original_filename)

class GmailLink(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    gmail_message_id = db.Column(db.String(240), db.ForeignKey('gmail_message.id'))
    link = db.Column(db.Text())
    domain = db.Column(db.Text())

    def __repr__(self):
        return '<g-link {}>'.format(self.id)

class SlackAttachment(db.Model):
    md5 = db.Column(db.Text(), primary_key=True)
    slack_message_ts = db.Column(db.String(40), db.ForeignKey('slack_message.ts'), primary_key=True)
    slack_user_id = db.Column(db.String(20))
    size = db.Column(db.Integer)
    created = db.Column(db.Integer)
    timestamp = db.Column(db.Integer)
    id = db.Column(db.String(20))
    filename = db.Column(db.Text())
    filepath = db.Column(db.Text())
    title = db.Column(db.Text())
    mimetype = db.Column(db.Text())
    filetype = db.Column(db.Text())
    pretty_type = db.Column(db.Text())
    user_team = db.Column(db.String(20))
    editable = db.Column(db.Boolean())
    mode = db.Column(db.Text())
    is_external = db.Column(db.Boolean())
    external_type = db.Column(db.Text())
    is_public = db.Column(db.Boolean())
    public_url_shared = db.Column(db.Boolean())
    display_as_bot = db.Column(db.Boolean())
    username = db.Column(db.Text())
    url_private = db.Column(db.Text())
    url_private_download = db.Column(db.Text())
    media_display_type = db.Column(db.Text())
    thumb_pdf = db.Column(db.Text())
    thumb_pdf_w = db.Column(db.Integer)
    thumb_pdf_h = db.Column(db.Integer)
    permalink = db.Column(db.Text())
    permalink_public = db.Column(db.Text())
    is_starred = db.Column(db.Boolean())
    has_rich_preview = db.Column(db.Boolean())
    file_access = db.Column(db.Text())

    def __repr__(self):
        return '<s-attachment with filename {}>'.format(self.filename)

class SlackLink(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    slack_message_ts = db.Column(db.String(40), db.ForeignKey('slack_message.ts'))
    has_text = db.Column(db.Text())
    url = db.Column(db.Text())
    text = db.Column(db.UnicodeText())
    domain = db.Column(db.Text())
    content = db.Column(db.Text())

    def __repr__(self):
        return '<s-link with domain {}>'.format(self.domain)

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
        else:
            return '<g-message-text {}>'.format(self.text[:10])


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

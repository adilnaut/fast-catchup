from app import db


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), index=True, unique=True)
    email = db.Column(db.String(120), index=True, unique=True)
    password_hash = db.Column(db.String(128))

    def __repr__(self):
        return '<user {}>'.format(self.username)

class SlackUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(20), index=True, unique=True)
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
        return '<s-user {}-{}>'.format(self.user_id, self.name)

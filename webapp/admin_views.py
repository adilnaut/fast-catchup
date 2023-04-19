from webapp import admin, db
from webapp.models import (User, Workspace, AudioFile, Platform, AuthData, PriorityListMethod, PriorityItemMethod,
    PriorityItem, PriorityMessage, PriorityList, Session, SlackChannel, SlackUser, SlackMessage, SlackAttachment,
    SlackLink, GmailMessage, GmailLink, GmailUser, GmailAttachment, GmailMessageTag, GmailMessageText,
    GmailMessageListMetadata, GmailMessageLabel, Setting, PlatformColumn)
from flask_admin.contrib.sqla import ModelView

class MyModelView(ModelView):
    column_display_pk = True
    column_display_fk = True

class PriorityItemView(MyModelView):
    column_list = ['id', 'priority_list_id', 'priority_message_id', 'p_b', 'p_b_a', 'p_a_b', 'p_a', 'p_a_c', 'p_b_c'
        , 'p_a_b_c']

class PriorityItemMethodView(MyModelView):
    column_list = ['id', 'priority_item_id', 'priority_list_method_id', 'p_b_m_a']

admin.add_view(MyModelView(GmailMessageText, db.session))
admin.add_view(MyModelView(SlackMessage, db.session))
admin.add_view(MyModelView(GmailMessage, db.session))
admin.add_view(MyModelView(PriorityList, db.session))
admin.add_view(MyModelView(PriorityListMethod, db.session))
admin.add_view(PriorityItemView(PriorityItem, db.session))
admin.add_view(PriorityItemMethodView(PriorityItemMethod, db.session))
admin.add_view(MyModelView(PriorityMessage, db.session))
admin.add_view(MyModelView(AuthData, db.session))
admin.add_view(MyModelView(Session, db.session))
admin.add_view(MyModelView(AudioFile, db.session))
admin.add_view(MyModelView(Platform, db.session))
admin.add_view(MyModelView(Workspace, db.session))
admin.add_view(MyModelView(User, db.session))
admin.add_view(MyModelView(Setting, db.session))
admin.add_view(MyModelView(PlatformColumn, db.session))

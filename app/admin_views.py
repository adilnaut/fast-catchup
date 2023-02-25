from app import admin, db
from app.models import (GmailMessage, SlackMessage, PriorityList, PriorityListMethod,
    PriorityItem, PriorityItemMethod, PriorityMessage)
from flask_admin.contrib.sqla import ModelView

class MyModelView(ModelView):
    column_display_pk = True

class PriorityItemView(MyModelView):
    column_list = ['id', 'priority_list_id', 'priority_message_id', 'p_b', 'p_b_a', 'p_a_b', 'p_a']

admin.add_view(MyModelView(SlackMessage, db.session))
admin.add_view(MyModelView(GmailMessage, db.session))
admin.add_view(MyModelView(PriorityList, db.session))
admin.add_view(MyModelView(PriorityListMethod, db.session))
admin.add_view(PriorityItemView(PriorityItem, db.session))
admin.add_view(MyModelView(PriorityItemMethod, db.session))
admin.add_view(MyModelView(PriorityMessage, db.session))

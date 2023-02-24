from app import admin, db
from app.models import (GmailMessage, SlackMessage, PriorityList, PriorityListMethod,
    PriorityItem, PriorityItemMethod, PriorityMessage)
from flask_admin.contrib.sqla import ModelView

admin.add_view(ModelView(SlackMessage, db.session))
admin.add_view(ModelView(GmailMessage, db.session))
admin.add_view(ModelView(PriorityList, db.session))
admin.add_view(ModelView(PriorityListMethod, db.session))
admin.add_view(ModelView(PriorityItem, db.session))
admin.add_view(ModelView(PriorityItemMethod, db.session))
admin.add_view(ModelView(PriorityMessage, db.session))

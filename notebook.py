from app import app, db

app.app_context().push()

from app.models import PriorityItem, PriorityList, PriorityMessage, GmailMessage, GmailMessageLabel
query = PriorityItem.query.join(PriorityList).filter(PriorityList.platform_id==2)
results = query.all()
p_item = query.filter(PriorityItem.id == 49).first()
query = query.filter(PriorityList.id != p_item.priority_list_id)
p_m = PriorityMessage.query.filter_by(id=p_item.priority_message_id).first()
m_item = GmailMessage.query.filter_by(id=p_m.message_id).first()
columns_list = ['id', 'GmailMessageLabel.label']
from app.models import smart_filtering
r = smart_filtering(GmailMessage, columns_list, m_item, query)
# from app.models import cast_tuples_to_p_items
# result = cast_tuples_to_p_items(r)
for res in r:
    print(res)

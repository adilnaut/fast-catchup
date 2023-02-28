from quickstart.connection import db_ops, get_platform_id

def get_abstract_for_slack(slack_message):
    return slack_message.text, slack_message.ts

# def get_abstract_for_gmail(gmail_message):
#     return gmail_message.subject, gmail_message.id
def get_abstract_for_gmail(gmail_message):
    result_text = ""

    id_ = gmail_message.id
    email_ = gmail_message.gmail_user_email
    name_ = None
    snippet_ = None
    with db_ops(model_names=['GmailUser', 'GmailMessageText']) as \
        (db, GmailUser, GmailMessageText):
        platform_id = get_platform_id('gmail')
        gmail_user = GmailUser.query.filter_by(email=email_) \
            .filter_by(platform_id=platform_id) \
            .one()
        gm_snippet = GmailMessageText.query.filter_by(gmail_message_id=id_) \
            .filter_by(is_snippet=True).one()
        name_ = gmail_user.name
        snippet_ = gm_snippet.text
    subject_ = gmail_message.subject
    # date_ = gmail_message.date
    # date_ = convert_to_utc(date_).strftime('%m%d')
    # result_text += "%s emailed you %s with subject %s on %s\n" % (name_, snippet_, subject_, date_)
    result_text += "%s emailed %s with subject %s\n" % (name_, snippet_, subject_)

    return result_text, id_

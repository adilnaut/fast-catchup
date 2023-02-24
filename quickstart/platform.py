def get_abstract_for_slack(slack_message):
    return slack_message.text, slack_message.ts

def get_abstract_for_gmail(gmail_message):
    return gmail_message.subject, gmail_message.id

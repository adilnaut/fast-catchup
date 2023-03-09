from quickstart.connection import db_ops, get_platform_id
import torch
import time
import numpy as np
import os
import openai

from datetime import datetime, timedelta
from dateutil import parser
import pytz
import time
import requests
import hashlib

from openai.error import RateLimitError

from PyPDF2 import PdfReader
from nltk.tokenize import word_tokenize
from nltk.tokenize import sent_tokenize
from transformers import pipeline
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
from transformers import GPT2TokenizerFast



def get_abstract_for_slack(slack_message):
    return format_slack_message(slack_message, abstract_func=build_abstract_for_unbounded_text), slack_message.ts


def ts_to_formatted_date(ts):
    # dangerous timstamp handling
    return datetime.fromtimestamp(int(ts.split('.')[0])).strftime('%c')

# Opportunity: make it sqllite defined function?
def encapsulate_names_by_ids(text):
    platform_id = get_platform_id('slack')
    if '<@' in text.split('>')[0]:
        left = text.split('>')[0]
        middle = left.split('<@')[1]
        user_data = None
        with db_ops(model_names=['SlackUser']) as (db, SlackUser):
            user_data = SlackUser.query.filter_by(id=middle)  \
                .filter_by(platform_id=platform_id) \
                .first()
        if user_data:
            # user_data = slack_users.get(middle)
            user_name = user_data.name
            # user_data = slack_users.get(middle)
            # user_name = user_data.get('name')
            text = text.replace('<@%s>' % middle, user_name)
    return text

def format_slack_message(slack_message, abstract_func=None, date_string=False, channel_misc=False):
    text = slack_message.text
    user_id = slack_message.slack_user_id
    channel_id = slack_message.slack_channel_id
    ts = slack_message.ts

    user_data = None
    platform_id = get_platform_id('slack')
    with db_ops(model_names=['SlackUser']) as (db, SlackUser):
        if platform_id:
            user_data = SlackUser.query.filter_by(id=user_id)  \
                .filter_by(platform_id=platform_id) \
                .first()

    if user_data:
        user_name = user_data.name
        user_email = user_data.profile_email

        channel_data = None
    with db_ops(model_names=['SlackChannel']) as (db, SlackChannel):
        if platform_id:
            channel_data = SlackChannel.query.filter_by(id=channel_id) \
                .filter_by(platform_id=platform_id) \
                .first()

    if channel_data:
        channel_name = channel_data.name
        channel_topic = channel_data.topic
        channel_purpose = channel_data.purpose
        channel_is_channel = channel_data.is_channel
        channel_is_group = channel_data.is_group
        channel_is_im = channel_data.is_im

    # convert ts into datetime formatted string
    date_string = ts_to_formatted_date(ts)

    # encapsulate all mentions to real names by id
    text = encapsulate_names_by_ids(text)
    if len(text) > 50:
        text = abstract_func(text)

    result = 'Slack message:'
    result += ' with text \'%s\' ' % text
    if user_data and user_name:
        result += ' from %s ' % user_name
    if user_data and user_email:
        result += ' with email %s ' % user_email

    # we could also tell if it from channel, group or dm
    if channel_data and channel_is_channel:
        if channel_name:
            result += ' in a channel named %s ' % channel_name
        if channel_topic and channel_misc:
            result += ' with a channel topic %s ' % channel_topic
        if channel_purpose and channel_misc:
            result += ' with a channel purpose %s ' % channel_purpose
    elif channel_data and channel_is_group:
        # could also share num of mebers
        result += ' in a group conversation '
    elif channel_data and channel_is_im:
        result += ' in a direct message conversation '

    if date_string:
        result += ' at %s ' % date_string
    return result


def get_abstract_for_gmail(gmail_message):
    result_text = ""

    id_ = gmail_message.id
    email_ = gmail_message.gmail_user_email
    name_ = None
    snippet_ = None
    final_summary_ = None
    with db_ops(model_names=['GmailUser', 'GmailMessageText']) as \
        (db, GmailUser, GmailMessageText):
        platform_id = get_platform_id('gmail')
        gmail_user = GmailUser.query.filter_by(email=email_) \
            .filter_by(platform_id=platform_id) \
            .one()
        gm_snippet = GmailMessageText.query.filter_by(gmail_message_id=id_) \
            .filter_by(is_snippet=True).first()

        gm_texts = GmailMessageText.query.filter_by(gmail_message_id=id_).all()
        summaries = []
        for gm_text in gm_texts:
            print(len(gm_text.text))
            summaries.append(build_abstract_for_unbounded_text_2(gm_text.text))
        summary = '\n'.join(summaries)
        print(len(summary))
        final_summary_ = build_abstract_for_unbounded_text_2(summary)

        name_ = gmail_user.name
        snippet_ = gm_snippet.text
    subject_ = gmail_message.subject
    # date_ = gmail_message.date
    # date_ = convert_to_utc(date_).strftime('%m%d')
    # result_text += "%s emailed you %s with subject %s on %s\n" % (name_, snippet_, subject_, date_)
    result_text += "%s emailed starting with %s and summary %s and with subject %s\n" % (name_, snippet_,
        final_summary_, subject_)

    return result_text, id_

def summarize_with_gpt3(input_text):
    time.sleep(0.5)
    ''' Prompt ChatGPT or GPT3 level of importance of one message directly
        TODO: save not only parsed value but also explanation
        TODO: decice where None values should be handled and throw exception
    '''
    openai.api_key = os.getenv("OPEN_AI_KEY")
    # todo might be worth specifying what type of data a bit ( if not independent of metadata )
    prompt = 'Please tell what is the most important in the following text: %s' % input_text
    try:

        system_prompt = '''
            You are human work assistant, whose job is to get big chunk of texts
            and to pick the most important points or abstract summaries from text.
            You can either skip details or only get some details from the text,
            depending on what you think is important or what could be urgent.
            Especially if something in a text requires some action.
            If the text contain boilerplate advertisements or news, newsletters -
            you can safely tell that what the text is and give short abstractive summary.
            The most important text is personal, work-related or document related stuff
            - you should give abstractive summary and provide a note that
            there could be more important details and one should skim the whole document.
        '''
        response = openai.ChatCompletion.create(
              model="gpt-3.5-turbo",
              messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ]
            )
    except RateLimitError:
        return "You exceeded your current quota, please check your plan and billing details."
    # print(response)
    text_response = response['choices'][0]['message']['content']
    return text_response

def build_abstract_for_unbounded_text_2(text, truncate=False):
    chunk_length = 2500
    chunk_start = 0
    chunk_end = chunk_length
    tokenizer = GPT2TokenizerFast.from_pretrained("gpt2")
    tokens = tokenizer(text)
    inputs_batch_lst = []
    while chunk_start <= len(tokens):
        inputs_batch = tokens['input_ids'][chunk_start:chunk_end]
        in_text = ' '.join([ text[tokens.token_to_chars(i).start:tokens.token_to_chars(i).end] \
            for i in range(chunk_start + len(inputs_batch))])
        inputs_batch_lst.append(in_text)
        chunk_start += chunk_length
        chunk_end += chunk_length
    summaries = [summarize_with_gpt3(x) for x in inputs_batch_lst]
    summary = '\n'.join(summaries)
    return summary


def build_abstract_for_unbounded_text(text, truncate=False):
    # model_name="knkarthick/MEETING_SUMMARY"
    model_name="sshleifer/distilbart-cnn-12-6"
    model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    inputs_no_trunc = tokenizer(text, max_length=None, return_tensors='pt', truncation=truncate)
    chunk_start = 0
    chunk_end = tokenizer.model_max_length  # == 1024 for Bart
    inputs_batch_lst = []
    while chunk_start <= len(inputs_no_trunc['input_ids'][0]):
        inputs_batch = inputs_no_trunc['input_ids'][0][chunk_start:chunk_end]  # get batch of n tokens
        inputs_batch = torch.unsqueeze(inputs_batch, 0)
        inputs_batch_lst.append(inputs_batch)
        chunk_start += tokenizer.model_max_length  # == 1024 for Bart
        chunk_end += tokenizer.model_max_length  # == 1024 for Bart

    summary_ids_lst = [model.generate(inputs, num_beams=4, max_length=100, early_stopping=True) for inputs in inputs_batch_lst]

    # summary_ids_lst = [model.generate(inputs, max_length=100, do_sample=False) for inputs in inputs_batch_lst]

    # decode the output and join into one string with one paragraph per summary batch
    summary_batch_lst = []
    for summary_id in summary_ids_lst:
        summary_batch = [tokenizer.decode(g, skip_special_tokens=True, clean_up_tokenization_spaces=False) for g in summary_id]
        summary_batch_lst.append(summary_batch[0])
    summary_all = '\n'.join(summary_batch_lst)
    # print(summary_all)
    return summary_all

def test_doc_summary(filepath):
    texts = extract_text_from_pdf(filepath)
    summaries = []
    for text in texts:
        summaries.append(build_abstract_for_unbounded_text(text))
    print(summaries)
    summary = '\n'.join(summaries)
    final_summary = build_abstract_for_unbounded_text(summary)
    print(final_summary)


def extract_text_from_pdf(filepath):
    # creating a pdf reader object

    reader = PdfReader(filepath)
    # extracting text from page
    text = [page.extract_text() for page in reader.pages]
    return text

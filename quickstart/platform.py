from quickstart.connection import db_ops, get_platform_id
import torch
import numpy as np

from PyPDF2 import PdfReader
from nltk.tokenize import word_tokenize
from nltk.tokenize import sent_tokenize
from transformers import pipeline
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

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
            summaries.append(build_abstract_for_unbounded_text(gm_text.text))
        summary = '\n'.join(summaries)
        final_summary_ = build_abstract_for_unbounded_text(summary)

        name_ = gmail_user.name
        snippet_ = gm_snippet.text
    subject_ = gmail_message.subject
    # date_ = gmail_message.date
    # date_ = convert_to_utc(date_).strftime('%m%d')
    # result_text += "%s emailed you %s with subject %s on %s\n" % (name_, snippet_, subject_, date_)
    result_text += "%s emailed starting with %s and summary %s and with subject %s\n" % (name_, snippet_,
        final_summary_, subject_)

    return result_text, id_



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

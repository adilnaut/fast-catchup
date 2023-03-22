from __future__ import print_function

import os
import os.path

import json
import uuid
import openai

from datetime import datetime

from collections import OrderedDict
from openai.error import RateLimitError


import azure.cognitiveservices.speech as speechsdk


from quickstart.gmail_utils import get_gmail_comms, get_list_data_by_g_id
from quickstart.slack_utils import get_slack_comms, get_list_data_by_m_id

from quickstart.connection import db_ops, get_current_user
from quickstart.sqlite_utils import get_insert_query

def get_p_items_by_session(session_id=None):

    # we need short information to show on tabs
    # and summary to show on the right views
    list_body_l = []
    with db_ops(model_names=['PriorityItem', 'PriorityList', 'PriorityMessage', 'Platform', 'PriorityItemMethod']) \
        as (db, PriorityItem, PriorityList, PriorityMessage, Platform, PriorityItemMethod):
        # get a priority list instance for each platform
        p_lists = PriorityList.query.filter_by(session_id=session_id).all()
        for p_list in p_lists:
            platform_id = p_list.platform_id
            platform = Platform.query.filter_by(id=platform_id).first()
            platform_name = platform.name
            p_items = p_list.items
            for p_item in p_items:
                p_message = PriorityMessage.query.filter_by(id=p_item.priority_message_id).first()
                p_i_m = PriorityItemMethod.query.filter_by(priority_item_id=p_item.id) \
                    .filter(PriorityItemMethod.model_justification != None).first()
                if p_message:
                    message_id = p_message.message_id
                    if platform_name == 'slack':
                        list_body= get_list_data_by_m_id(message_id)
                    elif platform_name == 'gmail':
                        list_body = get_list_data_by_g_id(message_id)
                    # list_body['score'] = int(p_item.p_a_b_c*100.0)
                    if p_item.p_a:
                        list_body['score'] = int(p_item.p_a*100.0)
                    else:
                        list_body['score'] = int(p_item.p_a_b*100.0)
                    list_body['text_score'] = int(p_item.p_b_a*100.0)
                    list_body['id'] = p_message.id
                    if p_i_m:
                        list_body['model_justification'] = p_i_m.model_justification
                    list_body_l.append(list_body)

    sorted_results = sorted(
        list_body_l,
        key=lambda x: x['score'],
        reverse=True
    )
    return sorted_results




# todo handle API exceptions and bad results
def get_gpt_summary(session_id=None, verbose=True):
    openai.api_key = os.getenv("OPEN_AI_KEY")


    message_texts = []
    with db_ops(model_names=['PriorityItem', 'PriorityList', 'PriorityMessage']) as (db, \
        PriorityItem, PriorityList, PriorityMessage):
        # get a priority list instance for each platform
        p_lists = PriorityList.query.filter_by(session_id=session_id).all()
        for p_list in p_lists:
            p_items = p_list.items
            for p_item in p_items:
                p_message = PriorityMessage.query.filter_by(id=p_item.priority_message_id).first()
                if p_message:
                    message_texts.append((p_item.p_a_b, p_message.input_text_value))
    sorted_messages = sorted(
        message_texts,
        key=lambda x: x[0],
        reverse=True
    )
    # print(sorted_messages)
    input_text = '\n'.join(['text %s, score %s' % (text, int(score*100.0)) for score, text in sorted_messages])

    prompt = '''Here is a list of incoming messages with their priority scores.
        Please transform this list of message summaries to narrated text starting from most important:
        '''
    prompt = '%s%s' % (prompt, input_text)

    try:
        system_prompt = '''
            You are communications catch-up assistant
            whose task is to transform list of messages with assigned importance scores
            to narrated text or summary of missed messages.
            You just simply tell user what he missed.
            In case of slack messages you should mention the sender and channel.
            Do not return priority_scores.
            Do not return email subjects.
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
    if verbose:
        print(response)
    text_response = response['choices'][0]['message']['content']
    current_user = get_current_user()
    user_id = current_user.get_id()
    with db_ops(model_names=['Workspace']) as (db, Workspace):

        workspace = Workspace.query.filter_by(user_id=user_id).one()
        workspace_id = workspace.id
        label_kwargs = OrderedDict([('session_id', session_id)
            , ('workspace_id', workspace_id)
            , ('date', datetime.now().strftime('%m/%d/%Y, %H:%M'))
            , ('summary', text_response)])
        label_query = get_insert_query('session', label_kwargs.keys())
        db.session.execute(label_query, label_kwargs)

    return text_response



def get_seconds(duration):
    # td = timedelta(hours=0, minutes=0, seconds=float(duration))
    total_seconds = duration.total_seconds()
    return total_seconds

# generates file.wav
# todo:
#   generate audio with random name
#   return audio filepath/random name
def generate_voice_file(text_response, verbose=False):

    # Creates an instance of a speech config with specified subscription key and service region.
    # Replace with your own subscription key and service region (e.g., "westus
    speech_key, service_region = os.getenv("SPEECH_KEY"), os.getenv("SPEECH_REGION")
    speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=service_region)

    # Set the voice name, refer to https://aka.ms/speech/voices/neural for full list.
    #speech_config.speech_synthesis_voice_name = "en-US-AriaNeural"
    # Set either the `SpeechSynthesisVoiceName` or `SpeechSynthesisLanguage`.
    speech_config.speech_synthesis_language = "en-US"
    speech_config.speech_synthesis_voice_name = "en-US-JennyNeural"
    # speech_config.speech_synthesis_voice_name = "en-US-AIGenerate2Neural"

    filename = '%s-%s' % (uuid.uuid4().hex, 'audio.wav')
    filepath = os.path.join('file_store', filename)

    audio_config = speechsdk.audio.AudioOutputConfig(filename=filepath)
    # audio_config = speechsdk.audio.AudioOutputConfig(use_default_speaker=True)
    # Receives a text from console input.

    # Creates a speech synthesizer using the default speaker as audio output.
    speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)

    word_boundaries = []
    # speech_synthesizer.synthesis_word_boundary.connect(lambda evt: print(
    #     "Word boundary event received: {}, audio offset in ms: {}ms".format(evt, evt.audio_offset / 10000)))
    # print(text_response)
    # SpeechSynthesisWordBoundaryEventArgs(audio_offset=329750000, duration=0:00:00.100000, text_offset=562, word_length=1)
    speech_synthesizer.synthesis_word_boundary.connect(lambda evt: word_boundaries.append({'audio_offset': evt.audio_offset / 10000000 \
        , 'text_offset': evt.text_offset, 'word_length': evt.word_length, 'duration': get_seconds(evt.duration) }) )
    # Synthesizes the received text to speech.
    # The synthesized speech is expected to be heard on the speaker with this line executed.
    result = speech_synthesizer.speak_text_async(text_response).get()

    # Checks result.
    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        if verbose:
            print("Speech synthesized to speaker for text [{}]".format(text_response))
    elif result.reason == speechsdk.ResultReason.Canceled:
        cancellation_details = result.cancellation_details
        if verbose:
            print("Speech synthesis canceled: {}".format(cancellation_details.reason))
        if cancellation_details.reason == speechsdk.CancellationReason.Error:
            if cancellation_details.error_details:
                if verbose:
                    print("Error details: {}".format(cancellation_details.error_details))
        if verbose:
            print("Did you update the subscription info?")
    return filepath, word_boundaries

def generate_summary(session_id, get_last_session=False):

    with db_ops(model_names=['Session']) as (db, Session):
        sess = Session.query.filter_by(session_id=session_id).first()

    if not sess:
        if not get_last_session:
            unread_emails = get_gmail_comms(session_id=session_id)
            unread_slack = get_slack_comms(session_id=session_id)
        gpt_summary = get_gpt_summary(session_id=session_id)
    else:
        gpt_summary = sess.summary

    with db_ops(model_names=['AudioFile']) as (db, AudioFile):
        audio = AudioFile.query.filter_by(session_id=session_id).first()

    if not audio:
        file_path, word_boundaries = generate_voice_file(gpt_summary)
    else:
        file_path = audio.file_path
        word_boundaries = json.loads(audio.word_boundaries)

    return gpt_summary, file_path, word_boundaries

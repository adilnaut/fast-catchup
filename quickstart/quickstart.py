from __future__ import print_function

import os
import os.path

import json
import uuid
import openai


from openai.error import RateLimitError


import azure.cognitiveservices.speech as speechsdk



from quickstart.gmail_utils import get_gmail_comms
from quickstart.slack_utils import get_slack_comms

from quickstart.connection import db_ops




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
                    message_texts.append((p_item.p_a_b_c, p_message.input_text_value))
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
    return text_response




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
        , 'text_offset': evt.text_offset, 'word_length': evt.word_length, 'duration': evt.duration }) )
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
    if not get_last_session:
        unread_emails = get_gmail_comms(session_id=session_id)
        unread_slack = get_slack_comms(session_id=session_id)

    gpt_summary = get_gpt_summary(session_id=session_id)

    filepath, word_boundaries = generate_voice_file(gpt_summary)

    return gpt_summary, filepath, word_boundaries

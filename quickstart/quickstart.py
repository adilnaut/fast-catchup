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



# todo handle API exceptions and bad results
def get_gpt_summary(prompt, unread_emails, unread_slack, verbose=False):
    openai.api_key = os.getenv("OPEN_AI_KEY")

    prompt += unread_emails
    prompt += unread_slack

    try:
        response = openai.Completion.create(
                model="text-davinci-003",
                prompt=prompt,
                temperature=0.3,
                max_tokens=150,
                top_p=1,
                frequency_penalty=0,
                presence_penalty=0
                )
    except RateLimitError:
        return "You exceeded your current quota, please check your plan and billing details."
    if verbose:
        print(response)
    text_response = response['choices'][0]['text']
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
    return filepath

def generate_summary(session_id, prompt=None, cache_slack=False, cache_gmail=False):
    if not prompt:
        prompt = '''I\'ve got the following slack messages and emails today please give me a quick summary
            of only important messages with urgent matters first.:'''

    unread_emails = get_gmail_comms(use_last_cached_emails=cache_gmail)

    # from db
    unread_slack = get_slack_comms(use_last_cached_emails=cache_slack)

    gpt_summary = get_gpt_summary(prompt, unread_emails, unread_slack)

    filepath = generate_voice_file(gpt_summary)

    return prompt, gpt_summary, filepath

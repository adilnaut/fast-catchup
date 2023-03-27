import os
import re
import time
import openai

from openai.error import RateLimitError
from openai.error import Timeout
from openai.error import APIConnectionError

from retry import retry
from transformers import pipeline
import transformers
from transformers import BloomForCausalLM
from transformers import BloomTokenizerFast
from transformers import AutoTokenizer
from transformers import AutoModelForCausalLM
import torch

import requests

def ask_large_bloom_raw(prompt, temperature=1.0, do_sample=True, top_k=20, top_p=0.2):
    time.sleep(1)
    API_URL = "https://api-inference.huggingface.co/models/bigscience/bloomz"
    headers = {"Authorization": f"Bearer %s" % os.environ['HUGGINGFACE_TOKEN']}

    def query(payload):
        response = requests.post(API_URL, headers=headers, json=payload)
        # print(response)
        return response.json()

    output = query({
        "inputs": prompt
        , "temperature": temperature
        , "do_sample": do_sample
        , "top_k": top_k
        , "top_p": top_p
    })
    if 'error' in output:
        # ask_instruct_bloom(input_text)
        print(output)
        print('Error in large bloom')
        exit()
    else:
        out_text = output[0]['generated_text']
    out_text = out_text.replace(prompt, '')
    return out_text

def ask_large_bloom(input_text):

    justification = ""
    # first ask the reasons why email is important
    prompt = '%s The thing that makes this email important is'
    prompt = prompt % input_text

    out_text = ask_large_bloom_raw(prompt)
    justification += 'The thing that makes this email important is' + out_text

    prompt += out_text

    # then ask the reason why email is not important
    second_prompt = '%s The thing that makes this email not important is'
    out_text = ask_large_bloom_raw(second_prompt % input_text)

    justification += 'The thing that makes this email not important is' + out_text
    prompt += second_prompt + out_text

    # then ask to classify
    prompt += '. With all that in mind the email importance score out of 10 is'
    # prompt += 'With all that in mind the email importance class (\'not important\', \'less than medium\', \'medium\', \'more than medium\', \'very important\') is '
    out_text = ask_large_bloom_raw(prompt)

    priority_score = parse_bloom_response(out_text)
    priority_score = int(priority_score)*0.1 if priority_score else None

    return priority_score, justification




def parse_gpt_response(text_response):
    tokens = text_response.split(' ')
    int_vals = []
    for token in tokens:
        int_val = int(token) if token and token.isdecimal() else None
        if int_val and int_val <= 100 and int_val >= 0:
            int_vals.append(int_val)
    # if there are multiple values, take first one
    # but later check keywords like 'out of '
    # i.e. 20 out of 100
    return int_vals[0]*0.01 if int_vals else 0



def parse_bloom_response(text_response):
    nums = re.findall(r'\d+', text_response)
    return nums[0] if nums else None

def ask_instruct_bloom(inp_text):
    prompt = prompt='''
    #Make sure priority indicate how important email text is
    Emails: [
    {id:1, text: \"Hey this is dave we need those report ASAP call me!\", priority:'High because it is about work and have ASAP word'},
    {id:2, text: \"Your weekly fun image digest\", priority:'low because it's not important newsletter/entertainment},
    {id:3, text: \"%s\", priority:
    '''
    response = ask_instruct_bloom_helper(inp_text, prompt, top_k=50, top_p=0.2)
    print(response)
    priority_score = parse_bloom_response(response)
    print("Score: %s " % priority_score)
    return priority_score

def ask_instruct_bloom_raw(prompt, top_k=10, top_p=0.2):
    tokenizer = AutoTokenizer.from_pretrained("mrm8488/bloom-560m-finetuned-unnatural-instructions")

    model = AutoModelForCausalLM.from_pretrained("mrm8488/bloom-560m-finetuned-unnatural-instructions")

    result_length = 105
    inputs = tokenizer(prompt, return_tensors="pt")
    # greedy
    text_response = tokenizer.decode(model.generate(inputs["input_ids"],
                       max_length=result_length,
                       early_stopping=True
                       # temperature=temperature
                       )[0])
    # top k
    # text_response = tokenizer.decode(model.generate(inputs["input_ids"],
    #                    max_length=result_length,
    #                    do_sample=True,
    #                    top_k=top_k,
    #                    top_p=top_p
    #                    # num_beams=3,
    #                    # no_repeat_ngram_size=2,
    #                    # early_stopping=True
    #                   )[0])
    text_response = text_response.replace(prompt, '')
    return text_response

def ask_instruct_bloom_helper(input_text, prompt=None, temperature=1.0, top_k=50, top_p=0.9):
    tokenizer = AutoTokenizer.from_pretrained("mrm8488/bloom-560m-finetuned-unnatural-instructions")

    model = AutoModelForCausalLM.from_pretrained("mrm8488/bloom-560m-finetuned-unnatural-instructions")

    if not prompt:
        prompt = '''Here I would print one email I\'ve got in my inbox. I also written manual metrics after
        email subjects to later help me to classify them. For example one of them is email importance.
        It is a score from 0 to 100. This score tells us how quick I should look at this email.
        Here is email info: email subject is "%s", email importance score is
        '''

    prompt = prompt % input_text
    result_length = len(prompt) + 2
    inputs = tokenizer(prompt, return_tensors="pt")
    # greedy
    # text_response = tokenizer.decode(model.generate(inputs["input_ids"],
    #                    max_length=result_length,
    #                    temperature=temperature
    #                    )[0])
    # top k
    text_response = tokenizer.decode(model.generate(inputs["input_ids"],
                       max_length=result_length,
                       temperature=temperature,
                       # top k
                       do_sample=True,
                       top_k=top_k,
                       top_p=top_p
                       # num_beams=3,
                       # no_repeat_ngram_size=2,
                       # early_stopping=True
                      )[0])
    text_response = text_response.replace(prompt, '')
    return text_response

def ask_bloom(input_text, temperature=1.0, top_k=50, top_p=0.9):
    model = BloomForCausalLM.from_pretrained("bigscience/bloom-1b1")
    tokenizer = BloomTokenizerFast.from_pretrained("bigscience/bloom-1b1")
    result_length = 150
    prompt = '''Here I would list the emails I\'ve got in my inbox. I also written various manual metrics after
    email subjects to later help me to classify them. For example one of them is email importance.
    It is a score from 0 to 100. This score tells us how quick I should look at this email.
    Then I provided reason for it's priority/importance. Here are emails:
    1. Email subject: "%s", Email importance score:
    '''
    prompt = prompt % input_text
    inputs = tokenizer(prompt, return_tensors="pt")
    # greedy
    # text_response = tokenizer.decode(model.generate(inputs["input_ids"],
    #                    max_length=result_length,
    #                    temperature=temperature
    #                   )[0])
    # top k
    text_response = tokenizer.decode(model.generate(inputs["input_ids"],
                       max_length=result_length,
                       temperature=temperature,
                       do_sample=True,
                       top_k=top_k,
                       top_p=top_p
                      )[0])
    text_response = text_response.replace(prompt, '')
    print('Text response for <<%s>> is <<%s>>' % (input_text, text_response))
    priority_score = parse_gpt_response(text_response)
    return priority_score, None

@retry((Timeout, RateLimitError, APIConnectionError), tries=5, delay=1, backoff=2)
def ask_gpt(input_text):
    time.sleep(0.05)
    ''' Prompt ChatGPT or GPT3 level of importance of one message directly
        TODO: save not only parsed value but also explanation
        TODO: decice where None values should be handled and throw exception
    '''
    openai.api_key = os.getenv("OPEN_AI_KEY")
    # todo might be worth specifying what type of data a bit ( if not independent of metadata )
    prompt = 'Rate this message text from 0 to 100 by level of importance: %s' % input_text

    system_prompt = '''
        You are assisting human with incoming messages prioritisation.
        Please try to guess what emails are generic or sent automatically and
        non-urgent and don't give them scores above 50.
        Above 50 is for emails that need actions from receiving person.
        Please keep advertisements under 20.
        Slack messages are not less important than emails.
        Work related slack messages and not requiring actions from 40 to 60.
        And work related  slack messages and requiring actions from you should be around 80.
    '''
    response = openai.ChatCompletion.create(
          model="gpt-3.5-turbo",
          messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]
          , timeout=20
          , max_tokens=100
        )

    text_response = response['choices'][0]['message']['content']

    priority_score = parse_bloom_response(text_response)
    model_justification = text_response.replace('%s ' % priority_score, '')
    priority_score = int(priority_score)*0.01 if priority_score else None
    return priority_score, model_justification


def toy_keyword_match(input_text):
    ''' if match hardcoded keywords return 1 else 0
    '''
    keywords = ['urgent', 'important', 'billing', 'asap']
    for keyword in keywords:
        if keyword in input_text.lower():
            return 1, None
    return 0, None

def sentiment_analysis(input_text):
    ''' get transformered sentiment analysis value
        but only negative one, with a score
        if positive return 0
    '''
    # todo load locally
    sentiment_pipeline = pipeline("sentiment-analysis")
    data = []
    data.append(input_text)
    result = sentiment_pipeline(data)
    label = result[0].get('label')
    score = result[0].get('score')
    print('sentiment')
    print(label)
    print(score)
    if label == 'NEGATIVE':
        return score, None
    else:
        return 0, None

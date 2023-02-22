import openai
from transformers import pipeline


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
    return int_vals[0]*0.01 if int_vals else None

def ask_gpt(input_text):
    ''' Prompt ChatGPT or GPT3 level of importance of one message directly
        TODO: save not only parsed value but also explanation
        TODO: decice where None values should be handled and throw exception
    '''
    openai.api_key = os.getenv("OPEN_AI_KEY")
    # todo might be worth specifying what type of data a bit ( if not independent of metadata )
    prompt = 'Rate this message text from 0 to 100 by level of importance: %s' % input_text
    try:
        # at this stage as text-davinci-003
        # however
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
    text_response = response['choices'][0]['text']
    priority_score = parse_gpt_response(text_response)
    return priority_score


def toy_keyword_match(input_text):
    ''' if match hardcoded keywords return 1 else 0
    '''
    keywords = ['urgent', 'important', 'billing', 'asap']
    if input_text.lower() in keywords:
        return 1
    else:
        return 0

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
    if label == 'NEGATIVE':
        return score
    else:
        return 0

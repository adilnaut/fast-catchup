import tweepy
import os
import json
import time
import re
import openai

from openai.error import RateLimitError
from openai.error import Timeout
from openai.error import APIConnectionError
from retry import retry

# API keyws that yous saved earlier
api_key =  os.getenv("TWITTER_API_KEY")
api_secrets = os.getenv("TWITTER_API_KEY_SECRET")
access_token = os.getenv("TWITTER_ACCESS_TOKEN")
access_secret = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")

assert api_key
assert api_secrets
assert access_token
assert access_secret

# Authenticate to Twitter
auth = tweepy.OAuthHandler(api_key,api_secrets)
auth.set_access_token(access_token,access_secret)

api = tweepy.API(auth)

try:
    api.verify_credentials()
    print('Successful Authentication')
except:
    print('Failed authentication')

@retry((Timeout, RateLimitError, APIConnectionError), tries=5, delay=1, backoff=2)
def gpt_request_wrapper(prompt, system_prompt):
    time.sleep(0.05)
    openai.api_key = os.getenv("OPEN_AI_KEY")

    prompt = prompt

    response = openai.ChatCompletion.create(
          model="gpt-3.5-turbo",
          messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
          timeout=50,
          temperature=2
        )

    text_response = response['choices'][0]['message']['content']
    return text_response

def get_user_by_id(user_id):
    # user = api.get_user(id=user_id) # Store user as a variable

    # Get user Twitter statistics
    # print(f"user.followers_count: {user.followers_count}")
    # print(f"user.listed_count: {user.listed_count}")
    # print(f"user.statuses_count: {user.statuses_count}")

    # Show followers
    # for follower in user.followers()[:10]:
        # print('Name: ' + str(follower.name))
        # print('Username: ' + str(follower.screen_name))

    # Follow a user
    # api.create_friendship('ChouinardJC')

    # Get tweets from a user tmeline
    # tweets = api.user_timeline(id=user_id, tweet_mode='extended', count=20)
    tweets = api.home_timeline(tweet_mode='extended', count=50)
    # tweets_extended = api.user_timeline(id=user_id, tweet_mode='extended', count=200)

    tweet = tweets[0]
    saved_tweets = []
    assigned_topics = []
    for tweet in tweets[10:20]:
        json = tweet._json
        # print(json.keys())
        f_text = json.get('full_text')
        f_test =  re.findall("[\dA-Za-z]*", f_text)[0]

        if not f_test:
            continue
        system_prompt = 'You are topic assigner. You see a tweet, you assign a specific topic to it!'
        prompt = 'Assign a specific topic to the following tweet %s. Topic shouldn\'t be longer than 4 word phrase.' % f_text
        # print(f_text)
        topic = gpt_request_wrapper(prompt, system_prompt)
        print(topic)
        assigned_topics.append(topic)
        saved_tweets.append((f_text, topic))

    # status = gpt_request_wrapper('\n'.join(saved_tweets))
    # print(status)
    # system_prompt = '''You are topic chooser. You see a list of topics and choose the most interesting one.
    #     You interested in tech and startup world, but can sometimes go into different topics if they are exciting.
    #     Avoid politics, you don't like politics. Do not offend anyone.'''
    #
    #
    # prompt = 'Here is a list of topics %s, please say the reason why one of them is the most interesting and then choose one' % '\n'.join(assigned_topics)
    # chosen_topic = gpt_request_wrapper(prompt, system_prompt)
    # print(saved_tweets)
    # print(chosen_topic)
    system_prompt = '''You are twitter writer. You are smart, not snarky very calm and rational. \
    You provide good commentary and value to discussions.'''
    system_prompt_2 = '''You are shizo twitter poaster. You are meemy and ingroup niche celebrity.
    You are somewhat unhinged and exciting. You don't fear to tell the truth.'''

    for t_text, t_topic in saved_tweets:
        print("-----------TWEET---------------")
        print(t_topic)
        print(t_text)

        prompt = '''
        And here your chosen topic: %s .
        And here is example of a tweet on this topic %s.
        Now write a tweet on this topic. Do not use hastags. But remember this:
        You are shizo twitter poaster. You are meemy and ingroup niche celebrity.
        You are somewhat unhinged and exciting.
        Don't call people to do or discuss something in your tweet.
        Don't write let's do that or this in your tweet.
        Just observe and share your observation.''' % (t_text, t_topic)
        tweet_out = gpt_request_wrapper(prompt, system_prompt_2)
        print(tweet_out)
        new_prompt = '''
            Here is a tweet %s. I think this tweet is a lame - it doesn't feel original it feels forced.
            Please transform it to add more substance, make it not lame.
        ''' % tweet_out
        new_tweet = gpt_request_wrapper(new_prompt, system_prompt)
        print(new_tweet)

        new_prompt = '''
            Here is a tweet that sounds a little boring %s. Could you transform it to something humorous, something
            more insightful and unexpected.
        ''' % new_tweet

        new_tweet = gpt_request_wrapper(new_prompt, system_prompt_2)
        print(new_tweet)
        print("-----------END--TWEEET---------------\n\n")
    # api.update_status(status=status)
    # Like or retweet tweets
    # id = 'id_of_tweet' # tweet ID
    # tweet = api.get_status(id) # get tweets with specific id
    # tweet.favorite() # Like a tweet
    # tweet.retweet() # Retweet

get_user_by_id('TuleuovAdilet')

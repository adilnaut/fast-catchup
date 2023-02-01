import os


from flask import render_template, send_file, request
from app import app
from quickstart.quickstart import generate_summary, get_slack_comms, get_gmail_comms
from quickstart.slack_utils import get_slack_comms



@app.route('/first', methods=['GET'])
def first():
    # unread_slack = list(get_slack_comms(return_dict=True).values())
    unread_slack = get_slack_comms(return_list=True)

    # print(unread_slack)

    unread_gmail = list(get_gmail_comms(return_dict=True).values())

    gptin = {'slack_list': unread_slack,
             'gmail_list': unread_gmail,
             'prompt': 'Here are my slack and email texts could you summarize them?'}
    gptout = {'summary': 'Press Generate to generate summary'}

    return render_template('first.html', title='Home', gptin=gptin, gptout=gptout)

@app.route('/generate_summary', methods=['POST'])
def gen_summary():
    gptin = {}
    gptout = {}
    prompt = '''I\'ve got the following slack messages and emails today please give me a quick summary
        of only important messages with urgent matters first.:'''
    unread_slack = list(get_slack_comms(return_dict=True).values())
    unread_gmail = list(get_gmail_comms(return_dict=True).values())


    # get prompt from post form
    _ = request.form['prompt']
    if _:
        prompt = _

    cache_slack = request.form.get("slack-checkbox") != None
    cache_gmail = request.form.get("gmail-checkbox") != None

    # try:
    prompt, gpt_summary, filepath = generate_summary(prompt=prompt,
        cache_slack=cache_slack, cache_gmail=cache_gmail)

    gptin['slack_list'] = unread_slack
    gptin['gmail_list'] = unread_gmail
    gptin['prompt'] = prompt

    gptout['summary'] = gpt_summary
    # todo: throw meaningful exception in generate_summary and import exception class here
    # except:
    #     print('[Error] There was an error in generate summary!')
    #     gptin = {'slack_text': 'slack text 1, slack text 2',
    #              'email_text': 'email_text 1, email text 2',
    #              'prompt': 'Here are my slack and email texts could you summarize them?'}
    #     gptout = {'summary': 'You\'ve got slack text 1 and 2 and email 1 and 2'}

    # todo provide filepath to index.html template and adjust returnAudioFile method accordingly

    return render_template('first.html',title='Home', gptin=gptin, gptout=gptout)

@app.route('/', methods=['POST', 'GET'])
@app.route('/index')
def index():
    gptin = {}
    gptout = {}
    prompt = '''I\'ve got the following slack messages and emails today please give me a quick summary
        of only important messages with urgent matters first.:'''
    # get prompt from post form
    if request.method == 'POST':
        prompt = request.form['prompt']

    try:
        unread_emails, unread_slack, prompt, gpt_summary, filepath = generate_summary(prompt, cache_slack=cache_slack)

        gptin['slack_text'] = unread_slack
        gptin['email_text'] = unread_emails
        gptin['prompt'] = prompt

        gptout['summary'] = gpt_summary
    # todo: throw meaningful exception in generate_summary and import exception class here
    except:
        print('[Error] There was an error in generate summary!')
        gptin = {'slack_text': 'slack text 1, slack text 2',
                 'email_text': 'email_text 1, email text 2',
                 'prompt': 'Here are my slack and email texts could you summarize them?'}
        gptout = {'summary': 'You\'ve got slack text 1 and 2 and email 1 and 2'}

    # todo provide filepath to index.html template and adjust returnAudioFile method accordingly



    return render_template('index.html',title='Home', gptin=gptin, gptout=gptout)



@app.route('/audio/file.wav')
def returnAudioFile():
    path_to_audio_file = os.getcwd()+'\/app\/audio\/file.wav'
    return send_file(
            path_to_audio_file,
            mimetype='audio/wav',
            as_attachment=True,
            download_name='file.wav')

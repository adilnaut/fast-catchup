import os


from flask import render_template, send_file, request, flash, redirect, url_for
from flask_login import current_user, login_user, logout_user, login_required
from app import app, db
from app.models import User
from app.forms import LoginForm, RegistrationForm

from werkzeug.urls import url_parse

from quickstart.quickstart import generate_summary
from quickstart.slack_utils import get_slack_comms, list_sfiles, clear_slack_tables, slack_test_etl, list_slinks
from quickstart.gmail_utils import get_gmail_comms, test_etl, clean_gmail_tables, list_gtexts, list_gfiles, list_glinks


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password')
            return redirect(url_for('login'))
        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get('next')
        if not next_page or url_parse(next_page).netloc != '':
            next_page = url_for('index')
        return redirect(next_page)
    return render_template('login.html', title='Sign In', form=form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Congratulations, you are now a registered user!')
        return redirect(url_for('login'))
    return render_template('register.html', title='Register', form=form)



@app.route('/list_gmail_texts', methods=['GET'])
def list_gmail_texts():
    gtexts = list_gtexts()
    # print(gtexts)
    return render_template('gmail_texts.html', gtexts=gtexts)

@app.route('/list_gmail_files', methods=['GET'])
def list_gmail_files():
    gfiles = list_gfiles()
    # print(gtexts)
    return render_template('gmail_files.html', gfiles=gfiles)

@app.route('/list_gmail_links', methods=['GET'])
def list_gmail_links():
    glinks = list_glinks()
    # print(gtexts)
    return render_template('gmail_links.html', glinks=glinks)

@app.route('/list_slack_files', methods=['GET'])
def list_slack_files():
    sfiles = list_sfiles()
    return render_template('slack_files.html', sfiles=sfiles)

@app.route('/list_slack_links', methods=['GET'])
def list_slack_links():
    slinks = list_slinks()
    return render_template('slack_links.html', slinks=slinks)

@app.route('/test_gmail_etl', methods=['GET'])
def test_gmail_etl():
    test_etl()
    return "OK"

@app.route('/test_slack_etl', methods=['GET'])
def test_slack_etl():
    slack_test_etl()
    return "OK"

@app.route('/test_clear_gmail_table', methods=['GET'])
def test_clear_gmail_table():
    clean_gmail_tables()
    return "OK"

@app.route('/clear_slack_table', methods=['GET'])
def test_clear_slack_table():
    clear_slack_tables()
    return "OK"

@app.route('/first', methods=['GET'])
def first():
    unread_slack = get_slack_comms(return_list=True)
    unread_gmail = get_gmail_comms(return_list=True)

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
    unread_slack = get_slack_comms(return_list=True)
    unread_gmail = get_gmail_comms(return_list=True)


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

    return render_template('first.html', title='Home', gptin=gptin, gptout=gptout)


@app.route('/', methods=['POST', 'GET'])
@app.route('/index')
@login_required
def index():
    return render_template('index.html',title='Home')



@app.route('/audio/file.wav')
def returnAudioFile():
    path_to_audio_file = os.getcwd()+'\/app\/audio\/file.wav'
    return send_file(
            path_to_audio_file,
            mimetype='audio/wav',
            as_attachment=True,
            download_name='file.wav')

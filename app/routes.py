import os
from datetime import datetime


from flask import render_template, send_file, request, flash, redirect, url_for
from flask_login import current_user, login_user, logout_user, login_required
from app import app, db
from app.models import User, Workspace, AudioFile
from app.forms import LoginForm, RegistrationForm, GmailAuthDataForm


from werkzeug.utils import secure_filename
from werkzeug.urls import url_parse

from quickstart.quickstart import generate_summary
from quickstart.slack_utils import get_slack_comms, list_sfiles, clear_slack_tables, slack_test_etl, list_slinks
from quickstart.gmail_utils import get_gmail_comms, test_etl, clean_gmail_tables, list_gtexts, list_gfiles, list_glinks


@app.route('/upload_gmail_auth', methods=['GET', 'POST'])
def upload_gmail_auth():
    form = GmailAuthDataForm()

    if form.validate_on_submit():
        filename = secure_filename(form.file.data.filename)
        # todo when transition to azure file store, save to tempdir, upload to cloud
        #  and persist file url
        filepath = os.path.join('file_store', filename)
        form.file.data.save(filepath)

        user_id = current_user.get_id()

        workspace = Workspace.query.filter_by(user_id=user_id).one()
        workspace_id = workspace.id

        #  not an upsert cause no need to update values on conflict
        platform_query = '''INSERT OR IGNORE INTO platform (name, workspace_id, auth_method)
                VALUES(:name, :workspace_id, :auth_method) returning id;'''

        # platform auth methods: cookie, oauth,
        platform_kwargs = {'name': 'gmail'
            , 'workspace_id': workspace_id
            , 'auth_methods': 'oauth'}

        platform_row = db.session.execute(platform_query, token_kwargs).fetchall()
        platform_id = platform_row.id

        credfile_query = '''INSERT INTO auth_data (platform_id, name, is_path, is_blob, is_data, file_data)
            VALUES(:platform_id, :name, :is_path, :is_blob, :is_data, :file_path)
            ON CONFLICT(platform_id, name)
            DO UPDATE SET file_path=excluded.file_path;'''

        credfile_kwargs = {'platform_id': platform_id
            , 'name': 'credentials.json'
            , 'is_path': True
            , 'is_blob': False
            , 'is_data': False
            , 'file_path': filepath}

        db.session.execute(credfile_query, credfile_kwargs)
        db.session.commit()

        # todo save filepath to database
        return redirect(url_for('index'))

    return render_template('upload_gmail_auth.html', form=form)

@app.route('/upload_slack_auth', methods=['GET', 'POST'])
@login_required
def upload_slack_auth():
    form = SlackAuthDataForm()
    if form.validate_on_submit():
        app_token = form.slack_app_token.data
        signing_secret = form.slack_signing_secret.data

        user_id = current_user.get_id()

        workspace = Workspace.query.filter_by(user_id=user_id).one()
        workspace_id = workspace.id
        #  not an upsert cause no need to update values on conflict
        platform_query = '''INSERT OR IGNORE INTO platform (name, workspace_id, auth_method)
                VALUES(:name, :workspace_id, :auth_method) returning id;'''

        # platform auth methods: slack_bot, cookie
        platform_kwargs = {'name': 'slack'
            , 'workspace_id': workspace_id
            , 'auth_methods': 'slack_bot'}

        platform_row = db.session.execute(platform_query, token_kwargs).fetchall()
        platform_id = platform_row.id

        token_query = '''INSERT INTO auth_data (platform_id, name, is_data, is_path, is_blob, file_data)
            VALUES(:platform_id, :name, :is_data, :is_path, :is_blob, :file_data)
            ON CONFLICT(platform_id, name)
            DO UPDATE SET file_data=excluded.file_data;'''

        token_kwargs = {'platform_id': platform_id
            , 'name': 'SLACK_BOT_TOKEN'
            , 'is_data': True
            , 'is_path': False
            , 'is_blob': False
            , 'file_data': app_token}

        db.session.execute(token_query, token_kwargs)

        secret_query = '''INSERT INTO auth_data (platform_id, name, is_data, is_path, is_blob, file_data)
            VALUES(:platform_id, :name, :is_data, :is_path, :is_blob, :file_data)
            ON CONFLICT(platform_id, name)
            DO UPDATE SET file_data=excluded.file_data;'''

        secret_kwargs = {'platform_id': platform_id
            , 'name': 'SLACK_BOT_TOKEN'
            , 'is_data': True
            , 'is_path': False
            , 'is_blob': False
            , 'file_data': signing_secret}

        db.session.execute(secret_query, secret_kwargs)
        db.session.commit()

        return redirect(url_for('index'))

    return render_template('upload_slack_auth.html', form=form)

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

        #  not an upsert cause no need to update values on conflict
        workspace_query = ''' INSERT OR IGNORE INTO workspace (created, user_id)
            VALUES(:created, :user_id);'''


        timestamp = int(round(datetime.now().timestamp()))

        # platform auth methods: slack_bot, cookie
        workspace_kwargs = {'created': timestamp
            ,'user_id': user.id}

        db.session.execute(workspace_query, token_kwargs)
        db.session.commit()


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


    prompt, gpt_summary, filepath = generate_summary(prompt=prompt,
        cache_slack=cache_slack, cache_gmail=cache_gmail)

    gptin['slack_list'] = unread_slack
    gptin['gmail_list'] = unread_gmail
    gptin['prompt'] = prompt

    user_id = current_user.get_id()

    workspace = Workspace.query.filter_by(user_id=user_id).one()
    workspace_id = workspace.id
    timestamp = int(round(datetime.now().timestamp()))

    audio_kwargs = {'workspace_id': workspace_id
        , 'created': timestamp
        , 'file_path': filepath}

    audio_row = AudioFile(**audio_kwargs)
    db.session.add(audio_row)
    db.session.commit()

    gptout['filepath'] = filepath
    gptout['summary'] = gpt_summary


    return render_template('first.html', title='Home', gptin=gptin, gptout=gptout)


@app.route('/', methods=['POST', 'GET'])
@app.route('/index')
@login_required
def index():
    return render_template('index.html',title='Home')


@app.route('/audio/<filepath>')
def returnAudioFile(filepath):
    path_to_audio_file = os.path.join(os.getcwd, filepath)
    return send_file(
            path_to_audio_file,
            mimetype='audio/wav',
            as_attachment=True,
            download_name='audio.wav')

import os
import uuid
from datetime import datetime
from sqlalchemy.sql import text

from flask import render_template, send_file, request, flash, redirect, url_for
from flask_login import current_user, login_user, logout_user, login_required
from app import app, db
from app.models import (User, Workspace, AudioFile, Platform, AuthData, PriorityListMethod, PriorityItemMethod,
    PriorityItem, PriorityMessage, PriorityList)
from app.forms import LoginForm, RegistrationForm, GmailAuthDataForm, SlackAuthDataForm


from werkzeug.utils import secure_filename
from werkzeug.urls import url_parse

from quickstart.quickstart import generate_summary
from quickstart.slack_utils import get_slack_comms, clear_slack_tables, slack_test_etl
from quickstart.gmail_utils import get_gmail_comms, test_etl, clean_gmail_tables
from quickstart.priority_engine import create_priority_list_methods
from setup import setup_sentence_embeddings_model, setup_sentiment_analysis_model
from datetime import timedelta
from flask import send_from_directory

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/upload_gmail_auth', methods=['GET', 'POST'])
def upload_gmail_auth():
    form = GmailAuthDataForm()

    if form.validate_on_submit():
        filename = secure_filename(form.file.data.filename)
        print("Filename gmail auth: %s" % filename)
        filename = '%s-%s' % (uuid.uuid4().hex, filename)
        # todo when transition to azure file store, save to tempdir, upload to cloud
        #  and persist file url
        filepath = os.path.join('file_store', filename)
        form.file.data.save(filepath)
        print("Filepath gmail auth: %s" % filepath)

        user_id = current_user.get_id()

        workspace = Workspace.query.filter_by(user_id=user_id).one()
        workspace_id = workspace.id

        #  not an upsert cause no need to update values on conflict
        platform_query = '''INSERT OR IGNORE INTO platform (name, workspace_id, auth_method)
                VALUES(:name, :workspace_id, :auth_method) returning id;'''

        # platform auth methods: cookie, oauth,
        platform_kwargs = {'name': 'gmail'
            , 'workspace_id': workspace_id
            , 'auth_method': 'oauth'}

        platform_row = db.session.execute(text(platform_query), platform_kwargs).fetchone()
        if not platform_row:
            platform_row = Platform.query \
                .filter_by(name='gmail') \
                .filter_by(workspace_id=workspace_id) \
                .filter_by(auth_method='oauth') \
                .one()
        platform_id = platform_row.id

        credfile_query = '''INSERT INTO auth_data (platform_id, name, is_path, is_blob, is_data, file_path)
            VALUES(:platform_id, :name, :is_path, :is_blob, :is_data, :file_path)
            ON CONFLICT(platform_id, name)
            DO UPDATE SET file_path=excluded.file_path;'''

        credfile_kwargs = {'platform_id': platform_id
            , 'name': 'credentials.json'
            , 'is_path': True
            , 'is_blob': False
            , 'is_data': False
            , 'file_path': filepath}

        db.session.execute(text(credfile_query), credfile_kwargs)
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
            , 'auth_method': 'slack_bot'}

        platform_row = db.session.execute(text(platform_query), platform_kwargs).fetchone()
        if not platform_row:
            platform_row = Platform.query \
                .filter_by(name='slack') \
                .filter_by(workspace_id=workspace_id) \
                .filter_by(auth_method='slack_bot') \
                .one()
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

        db.session.execute(text(token_query), token_kwargs)

        secret_query = '''INSERT INTO auth_data (platform_id, name, is_data, is_path, is_blob, file_data)
            VALUES(:platform_id, :name, :is_data, :is_path, :is_blob, :file_data)
            ON CONFLICT(platform_id, name)
            DO UPDATE SET file_data=excluded.file_data;'''

        secret_kwargs = {'platform_id': platform_id
            , 'name': 'SLACK_SIGNING_SECRET'
            , 'is_data': True
            , 'is_path': False
            , 'is_blob': False
            , 'file_data': signing_secret}

        db.session.execute(text(secret_query), secret_kwargs)
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

        db.session.execute(text(workspace_query), workspace_kwargs)
        db.session.commit()



        return redirect(url_for('login'))
    return render_template('register.html', title='Register', form=form)


@app.route('/remove_users', methods=['GET'])
def remove_users():
    users = User.query.all()
    for user in users:
        db.session.delete(user)
    db.session.commit()
    return redirect(url_for('index'))



@app.route('/test_gmail_etl', methods=['GET'])
def test_gmail_etl():
    test_etl()
    return redirect(url_for('index'))

@app.route('/test_slack_etl', methods=['GET'])
def test_slack_etl():
    slack_test_etl()
    return redirect(url_for('index'))

@app.route('/clear_gmail_table', methods=['GET'])
def test_clear_gmail_table():
    clean_gmail_tables()
    return redirect(url_for('index'))

@app.route('/clear_slack_table', methods=['GET'])
def test_clear_slack_table():
    clear_slack_tables()
    return redirect(url_for('index'))

@app.route('/generate_summary', methods=['GET'])
@login_required
def first():
    unread_slack = []
    unread_gmail = []

    gptin = {'slack_list': unread_slack,
             'gmail_list': unread_gmail}
    gptout = {'summary': ' Press Generate to generate summary'}

    return render_template('generate_summary.html', title='Summary', gptin=gptin, gptout=gptout)

def get_seconds(duration):
    # td = timedelta(hours=0, minutes=0, seconds=float(duration))
    total_seconds = duration.total_seconds()
    return total_seconds

@app.route('/generate_summary', methods=['POST'])
@login_required
def gen_summary():
    gptin = {}
    gptout = {}
    session_id = uuid.uuid4().hex

    # unread_slack = get_slack_comms(return_list=True, session_id=session_id)
    # unread_gmail = get_gmail_comms(return_list=True, session_id=session_id)


    # cache_slack = request.form.get("slack-checkbox") != None
    get_last_session = request.form.get("session-checkbox") != None

    if get_last_session:
        session_id = db.session.execute(text('''
            SELECT session_id FROM priority_list WHERE id = (SELECT max(id) FROM priority_list);''')).fetchone()
        if session_id:
            session_id = session_id[0]
        else:
            flash('No previous sessions found!')
            redirect(url_for('first'))
    gpt_summary, filepath, word_boundaries = generate_summary(session_id=session_id, get_last_session=get_last_session)

    # gptin['slack_list'] = unread_slack
    # gptin['gmail_list'] = unread_gmail


    persist_audio = False
    if persist_audio:
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

    timed_text = []
    p_tags = []
    a_tags = []
    for wb in word_boundaries:
        start = wb['text_offset']
        end = wb['word_length'] + start
        a_text = gpt_summary[start:end]
        if '\n' in a_text:
            p_tags.append(' '.join(a_tags))
            a_tags = []
        a_tags.append('<a id=%s>%s</a>' % (wb['audio_offset'], a_text) )

        # highlight_text = gpt_summary[start:end]
        # all_text = gpt_summary[:start] + ' <mark> ' + highlight_text + ' </mark> ' + gpt_summary[end:]
        # timed_text.append('%s | %s' % (wb['audio_offset'], all_text))
        timed_text.append('%s | %s' % (wb['audio_offset'], get_seconds(wb['duration'])))

    if not p_tags:
        p_tags.append(' '.join(a_tags))
    # print(timed_text)
    gptout['word_boundaries'] = '\n'.join(timed_text)
    gptout['p_tags'] = '<p>'+ '</p><p>'.join(p_tags) + '</p>'
    # gptout['word_boundaries'] = timed_text

    return render_template('generate_summary.html', title='Summary', gptin=gptin, gptout=gptout)


@app.route('/', methods=['POST', 'GET'])
@app.route('/index')
@login_required
def index():
    auth_data = db.session.query(AuthData) \
        .join(Platform) \
        .join(Workspace) \
        .filter(Workspace.user_id == current_user.get_id()).all()
    # auth_data = AuthData.query.filter_by(platform_id=platform_id).all()
    return render_template('index.html',title='Home', auth_data=auth_data)

@app.route('/setup', methods=['GET'])
@login_required
def setup_workspace():
    setup_sentence_embeddings_model()
    setup_sentiment_analysis_model()
    return redirect(url_for('index'))

@app.route('/audio/<filepath>')
def returnAudioFile(filepath):
    path_to_audio_file = os.path.join(os.getcwd(), filepath)
    return send_file(
            path_to_audio_file,
            mimetype='audio/wav',
            as_attachment=True,
            download_name='audio.wav')

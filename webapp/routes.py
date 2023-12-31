import os
import uuid
import json
import logging
from datetime import datetime
from sqlalchemy.sql import text

from flask import render_template, send_file, request, flash, redirect, url_for
from flask_login import current_user, login_user, logout_user, login_required
from webapp import app, db
from webapp.models import (User, Workspace, AudioFile, Platform, AuthData, PriorityListMethod, PriorityItemMethod,
    PriorityItem, PriorityMessage, PriorityList, Session, SlackChannel, SlackUser, SlackMessage, SlackAttachment,
    SlackLink, GmailMessage, GmailLink, GmailUser, GmailAttachment, GmailMessageTag, GmailMessageText,
    GmailMessageListMetadata, GmailMessageLabel, Setting, PlatformColumn)
from webapp.forms import LoginForm, RegistrationForm, GmailAuthDataForm, SlackAuthDataForm, DevModeForm


from werkzeug.utils import secure_filename
from werkzeug.urls import url_parse

from quickstart.connection import clear_session_data
from quickstart.quickstart import generate_summary, get_p_items_by_session
from quickstart.slack_utils import get_slack_comms, clear_slack_tables, slack_test_etl
from quickstart.gmail_utils import get_gmail_comms, test_etl, clean_gmail_tables
from quickstart.priority_engine import create_priority_list_methods
from datetime import timedelta
from flask import send_from_directory

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/assign_priorities', methods=['POST'])
@login_required
def assign_priorities():
    item_id = request.form['item_id']
    range_value = request.form['range_value']
    p_item = PriorityItem.query.filter_by(priority_message_id=item_id).first()
    p_item.p_a = int(range_value)*0.01
    db.session.commit()
    return 'Success!'

@app.route('/upload_gmail_auth', methods=['GET', 'POST'])
@login_required
def upload_gmail_auth():
    form = GmailAuthDataForm()

    if form.validate_on_submit():
        filename = secure_filename(form.file.data.filename)
        logging.debug("Filename gmail auth: %s" % filename)
        filename = '%s-%s' % (uuid.uuid4().hex, filename)
        # todo when transition to azure file store, save to tempdir, upload to cloud
        #  and persist file url
        filepath = os.path.join('file_store', filename)
        form.file.data.save(filepath)
        logging.debug("Filepath gmail auth: %s" % filepath)

        user_id = current_user.get_id()

        workspace = Workspace.query.filter_by(user_id=user_id).one()
        workspace_id = workspace.id

        #  not an upsert cause no need to update values on conflict
        # platform_query = '''INSERT OR IGNORE INTO platform (name, workspace_id, auth_method)
        #         VALUES(:name, :workspace_id, :auth_method) returning id;'''
        platform_query = '''INSERT OR IGNORE INTO platform (name, workspace_id, auth_method)
                VALUES(:name, :workspace_id, :auth_method);'''

        # platform auth methods: cookie, oauth,
        platform_kwargs = {'name': 'gmail'
            , 'workspace_id': workspace_id
            , 'auth_method': 'oauth'}

        db.session.execute(text(platform_query), platform_kwargs)
        platform_row = Platform.query \
            .filter_by(name='gmail') \
            .filter_by(workspace_id=workspace_id) \
            .filter_by(auth_method='oauth') \
            .one()
        platform_id = platform_row.id

        # initial priority order
        columns_list = ['id', 'GmailMessageLabel.label', 'gmail_user_email', 'content_type']

        pcolumns_query = '''INSERT OR IGNORE INTO platform_column (platform_id, order_num, column_name)
            VALUES (:platform_id, :order_num, :column_name)
            ON CONFLICT(platform_id, column_name)
            DO UPDATE SET order_num=excluded.order_num;'''

        for i in range(len(columns_list)):
            pcolumns_kwargs = {'platform_id': platform_id
                , 'order_num': i
                , 'column_name': columns_list[i]}
            db.session.execute(text(pcolumns_query), pcolumns_kwargs)


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
                VALUES(:name, :workspace_id, :auth_method);'''


        # platform auth methods: slack_bot, cookie
        platform_kwargs = {'name': 'slack'
            , 'workspace_id': workspace_id
            , 'auth_method': 'slack_bot'}

        db.session.execute(text(platform_query), platform_kwargs)
        platform_row = Platform.query \
            .filter_by(name='slack') \
            .filter_by(workspace_id=workspace_id) \
            .filter_by(auth_method='slack_bot') \
            .one()
        platform_id = platform_row.id

        # initial priority order
        columns_list = ['ts', 'slack_channel_id', 'slack_user_id']

        pcolumns_query = '''INSERT OR IGNORE INTO platform_column (platform_id, order_num, column_name)
            VALUES (:platform_id, :order_num, :column_name)
            ON CONFLICT(platform_id, column_name)
            DO UPDATE SET order_num=excluded.order_num;'''

        for i in range(len(columns_list)):
            pcolumns_kwargs = {'platform_id': platform_id
                , 'order_num': i
                , 'column_name': columns_list[i]}
            db.session.execute(text(pcolumns_query), pcolumns_kwargs)

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

        # upload current channels and users
        slack_test_etl()
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

@app.route('/save_settings', methods=['GET', 'POST'])
@login_required
def save_settings():
    setting = Setting.query.filter_by(user_id=current_user.id).first()
    form = DevModeForm(pscore_method=setting.pscore_method, embedding_method=setting.embeddings
        , num_neighbors=setting.num_neighbors, num_gmail_msg=setting.num_gmail_msg
        , num_days_slack=setting.num_days_slack)
    # is_submitted() if no validation to trigger
    if form.validate_on_submit():
        pscore_method_val = form.pscore_method.data
        embedding_method_val = form.embedding_method.data
        num_neighbors_val = int(form.num_neighbors.data)
        num_gmail_msg_val = int(form.num_gmail_msg.data)
        num_days_slack_val = int(form.num_days_slack.data)

        # to get not form platform column data
        # request.form.get('field') instead of form.field.data
        # cause it's easier to manually define fields
        workspace = Workspace.query.filter_by(user_id=current_user.id).first()
        platforms = Platform.query.filter_by(workspace_id=workspace.id).all()
        for platform in platforms:
            pc_order = request.form.getlist('%s_order[]' % platform.name)
            if not pc_order:
                continue
            for i in range(len(pc_order)):
                pc_query = ''' INSERT
                    INTO platform_column (platform_id, order_num, column_name)
                    VALUES (:platform_id, :order_num, :column_name)
                    ON CONFLICT (platform_id, column_name)
                    DO UPDATE SET platform_id=excluded.platform_id
                        , column_name=excluded.column_name
                        , order_num=excluded.order_num;'''
                pc_kwargs = {'platform_id': platform.id
                    , 'order_num': i+1
                    , 'column_name': pc_order[i]}
                db.session.execute(text(pc_query), pc_kwargs)
                db.session.commit()

        # update settings
        setting_query = ''' INSERT
            INTO setting (user_id, pscore_method, embeddings, num_neighbors, num_gmail_msg, num_days_slack)
            VALUES (:user_id, :pscore_method, :embeddings, :num_neighbors, :num_gmail_msg, :num_days_slack)
            ON CONFLICT(user_id)
            DO UPDATE SET user_id=excluded.user_id
                , pscore_method=excluded.pscore_method
                , embeddings=excluded.embeddings
                , num_neighbors=excluded.num_neighbors
                , num_gmail_msg=excluded.num_gmail_msg
                , num_days_slack=excluded.num_days_slack;'''
        setting_kwargs = {'user_id': current_user.id
            , 'pscore_method': pscore_method_val
            , 'embeddings': embedding_method_val
            , 'num_neighbors': num_neighbors_val
            , 'num_gmail_msg': num_gmail_msg_val
            , 'num_days_slack': num_days_slack_val}

        db.session.execute(text(setting_query), setting_kwargs)
        db.session.commit()
        flash('Values recorded Successfully!')
        redirect(url_for('index'))
    workspace = Workspace.query.filter_by(user_id=current_user.id).first()
    platforms = Platform.query.filter_by(workspace_id=workspace.id).all()
    # platforms is a list of dict objects with name and body keys
    # each platform body element is a coulmns dict with column_name and column_order_num keys
    platform_list = []
    for platform in platforms:
        p_dict = {}
        p_dict['name'] = platform.name
        body_list = []
        platform_columns = PlatformColumn.query.filter_by(platform_id=platform.id).all()
        columns_list = [(pc.order_num, pc.column_name) for pc in platform_columns]
        columns_list = sorted(columns_list, key=lambda x: x[0])
        for c_order_num, c_name in columns_list[1:]:
            body_list.append({'column_name': c_name, 'column_order_num': c_order_num})
        p_dict['body'] = body_list
        platform_list.append(p_dict)
    return render_template('dev_mode.html', title='Settings', form=form, platforms=platform_list)

@app.route('/logout')
@login_required
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

        # create initial settings
        setting_query = ''' INSERT OR IGNORE
            INTO setting (user_id, pscore_method, embeddings, num_neighbors, num_gmail_msg, num_days_slack)
            VALUES (:user_id, :pscore_method, :embeddings, :num_neighbors, :num_gmail_msg, :num_days_slack);
        '''

        setting_kwargs = {'user_id': user.id
            , 'pscore_method': 'raw_llm'
            , 'embeddings': 'openai_ada_v2'
            , 'num_neighbors': 5
            , 'num_gmail_msg': 8
            , 'num_days_slack': 1}
        db.session.execute(text(setting_query), setting_kwargs)
        db.session.commit()



        return redirect(url_for('login'))
    return render_template('register.html', title='Register', form=form)



# replace with on cascade and make sure that appropriate file_store files would be deleted
@app.route('/clear_all_user_data', methods=['GET'])
@login_required
def delete_user_data():
    user_id = current_user.get_id()
    workspace = Workspace.query.filter_by(user_id=user_id).first()
    workspace_id = workspace.id
    platforms = Platform.query.filter_by(workspace_id=workspace_id).all()
    for platf in platforms:
        slack_channels = SlackChannel.query.filter_by(platform_id=platf.id).all()
        for sc in slack_channels:
            slack_messages = SlackMessage.query.filter_by(slack_channel_id=sc.id).all()
            for sm in slack_messages:
                slack_attch = SlackAttachment.query.filter_by(slack_message_ts=sm.ts).all()
                for sa in slack_attch:
                    filepath = sa.filepath
                    if filepath and os.path.exists(filepath):
                        os.remove(filepath)
                    db.session.delete(sa)
                slack_links = SlackLink.query.filter_by(slack_message_ts=sm.ts).all()
                for sl in slack_links:
                    db.session.delete(sl)
                db.session.delete(sm)
            db.session.delete(sc)
        slack_users = SlackChannel.query.filter_by(platform_id=platf.id).all()
        for su in slack_users:
            db.session.delete(su)

        gmail_users = GmailUser.query.filter_by(platform_id=platf.id).all()
        for gu in gmail_users:
            gmail_messages = GmailMessage.query.filter_by(gmail_user_email=gu.email).all()
            for gm in gmail_messages:
                g_tags = GmailMessageTag.query.filter_by(gmail_message_id=gm.id).all()
                for g_tag in g_tags:
                    db.session.delete(g_tag)
                g_list_metas = GmailMessageListMetadata.query.filter_by(gmail_message_id=gm.id).all()
                for g_list_meta in g_list_metas:
                    db.session.delete(g_list_meta)
                g_m_texts = GmailMessageText.query.filter_by(gmail_message_id=gm.id).all()
                for g_m_text in g_m_texts:
                    db.session.delete(g_m_text)
                g_m_labels = GmailMessageLabel.query.filter_by(gmail_message_id=gm.id).all()
                for g_m_label in g_m_labels:
                    db.session.delete(g_m_label)
                g_links = GmailLink.query.filter_by(gmail_message_id=gm.id).all()
                for g_link in g_links:
                    db.session.delete(g_link)
                g_attachments = GmailAttachment.query.filter_by(gmail_message_id=gm.id).all()
                for g_a in g_attachments:
                    filepath = g_a.filepath
                    if filepath and os.path.exists(filepath):
                        os.remove(filepath)
                    db.session.delete(g_a)
                db.session.delete(gm)
            db.session.delete(gu)

        auth_data = AuthData.query.filter_by(platform_id=platf.id).all()
        for ad in auth_data:
            if ad.is_path:
                filepath = ad.file_path
                if filepath and os.path.exists(filepath):
                    os.remove(filepath)
            db.session.delete(ad)
        p_lists = PriorityList.query.filter_by(platform_id=platf.id).all()
        for p_list in p_lists:
            p_items = PriorityItem.query.filter_by(priority_list_id=p_list.id).all()
            for p_item in p_items:
                p_i_methods = PriorityItemMethod.query.filter_by(priority_item_id=p_item.id).all()
                for p_i_m in p_i_methods:
                    db.session.delete(p_i_m)
                db.session.delete(p_item)
            db.session.delete(p_list)
        p_messages = PriorityMessage.query.filter_by(platform_id=platf.id).all()
        for p_m in p_messages:
            db.session.delete(p_m)
        p_list_methods = PriorityListMethod.query.filter_by(platform_id=platf.id).all()
        for p_l_m in p_list_methods:
            db.session.delete(p_l_m)

        db.session.delete(platf)
    sessions = Session.query.filter_by(workspace_id=workspace_id).all()
    for sess in sessions:
        audio_file = AudioFile.query.filter_by(session_id=sess.session_id).first()
        if audio_file:
            filepath = audio_file.file_path
            if filepath and os.path.exists(filepath):
                os.remove(filepath)
            db.session.delete(audio_file)
        db.session.delete(sess)
    db.session.delete(workspace)
    db.session.delete(current_user)
    db.session.commit()
    flash('Successfully deleted all user data, message attachments, tokens and files!')
    return redirect(url_for('login'))

@app.route('/remove_session', methods=['GET'])
@login_required
def remove_session():
    session_id = request.args.get('session_id')
    clear_session_data(session_id=session_id)
    return redirect(url_for('first'))


@app.route('/generate_summary', methods=['GET'])
@login_required
def first():
    session_id = request.args.get('session_id')

    gptout = {}

    if not session_id:
        gptout['summary'] = ' Press Generate to generate summary'
        user_id = current_user.get_id()
        workspace = Workspace.query.filter_by(user_id=user_id).one()
        workspace_id = workspace.id
        past_sessions = Session.query.filter_by(workspace_id=workspace_id).all()
        gptout['past_sessions'] = [(p_sess.session_id, p_sess.date) for p_sess in past_sessions]
        return render_template('generate_summary.html', title='Summary', gptout=gptout)

    gpt_summary, filepath, word_boundaries = generate_summary(session_id=session_id)

    gptout['filepath'] = filepath
    gptout['sess_id'] = session_id

    gptout = build_tags_for_audio_highlight(session_id, gpt_summary, word_boundaries, gptout)

    return render_template('generate_summary.html', title='Summary', gptout=gptout)


def build_tags_for_audio_highlight(session_id, gpt_summary, word_boundaries, gptout):
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
        timed_text.append('%s | %s' % (wb['audio_offset'], wb['duration']))

    if not p_tags:
        p_tags.append(' '.join(a_tags))

    sorted_items = get_p_items_by_session(session_id=session_id)
    gptout['word_boundaries'] = '\n'.join(timed_text)
    gptout['p_tags'] = '<p>'+ '</p><p>'.join(p_tags) + '</p>'
    gptout['sorted_items'] = sorted_items

    user_id = current_user.get_id()
    workspace = Workspace.query.filter_by(user_id=user_id).one()
    workspace_id = workspace.id
    past_sessions = Session.query.filter_by(workspace_id=workspace_id).all()
    gptout['past_sessions'] = [(p_sess.session_id, p_sess.date) for p_sess in past_sessions]

    return gptout

def save_audio_data(session_id, word_boundaries, filepath):

    timestamp = int(round(datetime.now().timestamp()))
    audio_kwargs = {'session_id': session_id
        , 'created': timestamp
        , 'word_boundaries': json.dumps(word_boundaries)
        , 'file_path': filepath}

    audio_row = AudioFile(**audio_kwargs)
    db.session.add(audio_row)
    db.session.commit()

@app.route('/generate_summary', methods=['POST'])
@login_required
def gen_summary():
    gptout = {}
    session_id = uuid.uuid4().hex

    gpt_summary, filepath, word_boundaries = generate_summary(session_id=session_id)

    save_audio_data(session_id, word_boundaries, filepath)

    gptout['filepath'] = filepath
    gptout['sess_id'] = session_id

    gptout = build_tags_for_audio_highlight(session_id, gpt_summary, word_boundaries, gptout)

    return render_template('generate_summary.html', title='Summary', gptout=gptout)
    # return redirect(url_for('first', session_id=session_id), code=302)


    # return render_template('generate_summary.html', title='Summary', gptout=gptout)

@app.route('/get_neighbors', methods=['GET'])
@login_required
def get_neighbors():
    session_id = request.args.get('session_id', None)
    p_item_id = request.args.get('p_item_id', None)
    sess = Session.query.filter_by(session_id=session_id).first()
    if not sess or not sess.neighbors:
        return []
    n_s = json.loads(sess.neighbors)['slack']
    n_g = json.loads(sess.neighbors)['gmail']
    if n_s and n_g:
        nbrs_dict = n_s | n_g
    elif n_s:
        nbrs_dict = n_s
    elif n_g:
        nbrs_dict = n_g
    else:
        nbrs_dict = {}
    return nbrs_dict[p_item_id] if p_item_id in nbrs_dict else []

@app.route('/', methods=['POST', 'GET'])
@app.route('/index')
@login_required
def index():
    auth_data = db.session.query(AuthData) \
        .join(Platform) \
        .join(Workspace) \
        .filter(Workspace.user_id == current_user.get_id()).all()
    return render_template('index.html',title='Home', auth_data=auth_data)


# todo: check that user assoiciated with auth_id is current user
@app.route('/delete_auth/<auth_id>')
@login_required
def delete_auth(auth_id):
    auth_data = AuthData.query.filter_by(id=auth_id).first()
    db.session.delete(auth_data)
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/audio/<filepath>')
@login_required
def returnAudioFile(filepath):
    path_to_audio_file = os.path.join(os.getcwd(), filepath)
    return send_file(
            path_to_audio_file,
            mimetype='audio/wav',
            as_attachment=True,
            download_name='audio.wav')

from app import db
from sqlalchemy import func
from flask_login import UserMixin
from app import login
from werkzeug.security import generate_password_hash, check_password_hash
from sklearn.neighbors import NearestNeighbors
from sentence_transformers import SentenceTransformer
import numpy as np
import importlib
import pickle

@login.user_loader
def load_user(id):
    return User.query.get(int(id))


class PriorityList(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    platform_id = db.Column(db.Integer, db.ForeignKey('platform.id'))
    created = db.Column(db.Integer)
    p_a = db.Column(db.Float())

    def update_p_a(self):
        # average real importance of message
        result = db.session.query(func.avg(PriorityItem.p_a)) \
            .join(PriorityList) \
            .filter(PriorityList.platform_id == self.platform.id) \
            .all()
        self.p_a = result.as_scalar() if result else 0.3
        db.session.commit()

class PriorityListMethod(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    priority_list_id = db.Column(db.Integer, db.ForeignKey('priority_list.id'))
    p_m_a = db.Column(db.Float())
    name = db.Column(db.Text())
    python_path = db.Column(db.Text())

    def update_p_m_a(self):
        # which is # time method corr. when message is imp/ # imp messages
    	# for this particular method
    	# i.e. go over all priority_list table filter by same platform_id
    	# get all the items where p_a is important (i.e. > 0.7)
    	# get their according method data
    	# count number of where method_p_b_m_a close to p_b_a
    	# and divide by overall imp messages
        # average of  | p_b_m_a - p_b_a | * p_a
        #  incorrect cause one priority item have multiple priority methods
        #  consider either writing an sql query or just import data  and do that in python
        # result = db.session.query(func.avg(func.abs(PriorityItem.p_b_a - PriorityItemMethod) * PriorityItem.p_a ))
        query = PriorityList.query.filter_by(id=self.priority_list_id).first()
        platform_id = query.platform_id
        p_lists = PriorityList.query.filter_by(platform_id=platform_id).all()
        result = []
        for p_list in p_lists:
            # p_methods = PriorityListMethod.query.filter_by(priority_list_id=p_list.id).all()
            p_items = PriorityItem.query.filter_by(priority_list_id=p_list.id).all()
            for p_item in p_items:
                p_item_method = PriorityItemMethod.query \
                    .filter_by(priority_item_id=p_item.id) \
                    .filter_by(priority_list_method_id=self.id) \
                    .one()
                weighted_accuracy = abs(p_item_method.p_b_m_a - p_item.p_b_a) * p_item.p_a
                result.append(weighted_accuracy)
        self.p_m_a = np.array(result).mean()
        db.session.commit()


class PriorityItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    score = db.Column(db.Float())
    priority_list_id = db.Column(db.Integer, db.ForeignKey('priority_list.id'))
    priority_message_id = db.Column(db.Integer, db.ForeignKey('priority_message.id'))
    p_b = db.Column(db.Float())
    p_b_a = db.Column(db.Float())
    p_a_b = db.Column(db.Float())
    p_a = db.Column(db.Float())

    def calculate_p_b(self):
        # get priority_message vector
    	# get first k neighbors sample
    	# get number of important ones
    	# and divide by k

        # this is numpy array with either ChatGPT embedding, w2v embedding or sklearn bag of words
        p_m_vector = PriorityMessage.query.filter_by(id=self.priority_message_id).one().embedding_vector

        # ideally we should have 10 nearest neighbors classifiers object fitted on all previous data
        # but for now we can train it right there
        query = PriorityList.query.filter_by(id=self.priority_list_id).first()
        platform_id = query.platform_id
        p_lists = PriorityList.query.filter_by(platform_id=platform_id).all()
        ids = []
        all_vectors = []
        for p_list in p_lists:
            # p_methods = PriorityListMethod.query.filter_by(priority_list_id=p_list.id).all()
            p_items = PriorityItem.query.filter_by(priority_list_id=p_list.id).all()
            for p_item in p_items:
                _ = PriorityMessage.query.filter_by(id=p_item.priority_message_id).one()
                ids.append(_.id)
                all_vectors.append(_.embedding_vector)
        X = np.array(all_vectors)
        nbrs = NearestNeighbors(n_neighbors=10, algorithm='ball_tree').fit(X)

        distances, indices = nbrs.kneighbors(p_m_vector)
        p_as = []
        for n_i in indices:
            n_id = ids[n_i]
            n_item = PriorityItem.query.filter_by(id=n_id).one()
            p_as.append(n_item.p_a)
        self.p_b = np.array(p_as).mean()
        db.session.commit()

    def calculate_p_b_a(self):
        # get all priority_item methods and sum over
	    # assert p_m_a of all methods sum is one
        p_item_methods = PriorityItemMethod.query.filter_by(priority_item_id=self.id).all()
        sum = 0
        for p_item_method in p_item_methods:
            p_list_method = PriorityListMethod.query.filter_by(id=p_item_method.priority_list_method_id).one()
            p_m_a = p_list_method.p_m_a
            p_b_m_a = p_item_method.calculate_p_b_m_a()
            sum += p_b_m_a * p_m_a
        self.p_b_a = sum
        db.session.commit()


    def calculate_p_a_b(self):
        # call calculte_p_b_a
	    # call calculate_p_b
	    # p_a_b = p_b_a * p_a / p_b
        p_a = PriorityList.query.filter_by(id=self.priority_list_id).one().p_a
        self.p_a_b = self.p_b_a * p_a / self.p_b
        db.session.commit()

class PriorityItemMethod(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    priority_item_id = db.Column(db.Integer, db.ForeignKey('priority_item.id'))
    priority_list_method_id = db.Column(db.Integer, db.ForeignKey('priority_list_method.id'))
    p_b_m_a = db.Column(db.Float())

    def calculate_p_b_m_a(self):
        # call python method by name in PriorityMethod
	    # from priority_item, get priority_message and get text
        # here access p_list_method python path, import method by path and call python method
        # all methods should only take text into account
        priority_item = PriorityItem.query.filter_by(id=priority_item_id).one()
        priority_message = PriorityMessage.query.filter_by(id=priority_item.priority_message_id).one()
        inp_text = priority_message.input_text_value
        priority_list_method = PriorityListMethod.query.filter_by(id=priority_list_method_id).one()
        python_path = priority_list_method.python_path
        name = priority_list.name
        # how would python_path look like?
        #  python_path 'quickstart\priority_method.py'
        #  name 'ask_gpt'
        # todo:
        # check if python_path exists
        # check that attribute exists
        script_module = importlib.import_module(python_path)
        method_function = getattr(script_module, name)
        self.p_b_m_a = method_function(inp_text)
        db.session.commit()

class PriorityMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # implicit foreign key at this stage
    message_id = db.Column(db.Integer)
    input_text_value = db.Column(db.Text())
    embedding_vector = db.Column(db.LargeBinary)

    def enrich_input_text_value(self):
        # different platforms would get different methods of
	    # calculating abstracts or getting whole messages
	    # subjects or snippets for this
        # suppose there is a table that connects platform with their message table

        # with self.id you can get priority list id from priority_item
        priority_list_id = PriorityItem.query.filter_by(priority_message_id=self.id).one().id
        platform_id = PriorityList.query.filter_by(id=priority_list_id).one().platform_id
        platform_to_table = PlatformToMessageTables.query.filter_by(platform_id=platform_id).one()
        func_name = platform_to_table.func_name
        python_path = platform_to_table.python_path
        message_table_name = platform_to_table.message_table_name

        # for example
        #  python_path quickstart\platform.py
        #  func_name get_abstract_for_slack
        #  message_table_name slack_message


        abstract_builder_implemented = False
        # let's say this is an example of text summ method
        if not abstract_builder_implemented:
            self.input_text_value = db.session.execute(
                'SELECT text FROM %s WHERE id = :message_id;' % message_table_name,
                {'message_id': self.message_id})
        else:
            # but more general case is
            script_module = importlib.import_module(python_path)
            abstract_builder = getattr(script_module, func_name)
            self.input_text_value = abstract_builder()
        db.session.commit()


    def enrich_vectors(self):
        # at this stage just get w2v vector of input_text_value
        #  or even bag of words vectors
        #  0. plan where and when embedding builder will be called first and trained/fitted
        #  1. then it should be pickled and uploaded to file_store
        #  when this function will be called
        #  2. download pickle file from file_store
        #  3. use this object to embed input_text_value
        # at this stage pickle filepath would be hardcoded here
        # for reason it's a global file that wouldn't be versioned
        # it would be set up and called in setup.py root dir folder script
        # and there would be pickled


        # first unpickle embedding object
        model_filepath = os.path.join('file_store', '2023-02-22-embedding-model')
        model_pickle = open(model_filepath, 'rb')
        embedding_model = pickle.load(model_pickle)
        sentence = []
        sentence.append(self.input_text_value)
        self.embedding_vector = embedding_model.encode(sentence)
        db.session.commit()


class PlatformToMessageTable(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    platform_id = db.Column(db.Integer, db.ForeignKey('platform.id'), unique=True)
    message_table_name = db.Column(db.Text())
    python_path = db.Column(db.Text())
    func_name = db.Column(db.Text())

class AudioFile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspace.id'))
    created = db.Column(db.Integer)
    file_path = db.Column(db.Text())

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), index=True, unique=True)
    email = db.Column(db.String(120), index=True, unique=True)
    password_hash = db.Column(db.String(128))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return '<user {}>'.format(self.username)

class Workspace(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created = db.Column(db.Integer)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True)

    def __repr__(self):
        return '<workspace {}>'.format(self.id)

class Platform(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text())
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspace.id'))
    auth_method = db.Column(db.Text())
    __table_args__ = (db.UniqueConstraint('workspace_id', 'name', name='_unique_constraint_uc'),
        )

class AuthData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    platform_id = db.Column(db.Integer, db.ForeignKey('platform.id'))
    name = db.Column(db.Text())
    is_data = db.Column(db.Boolean())
    is_blob = db.Column(db.Boolean())
    is_path = db.Column(db.Boolean())
    file_data = db.Column(db.Text())
    file_blob = db.Column(db.Text())
    file_path = db.Column(db.Text())
    __table_args__ = (db.UniqueConstraint('platform_id', 'name', name='_unique_constraint_uc'),
        )


class SlackUser(db.Model):
    id = db.Column(db.String(20), primary_key=True)
    platform_id = db.Column(db.Integer, db.ForeignKey('platform.id'), primary_key=True)
    name = db.Column(db.String(120), index=True)
    team_id = db.Column(db.String(20), index=True)
    deleted = db.Column(db.Boolean())
    color = db.Column(db.String(20))
    real_name = db.Column(db.String(120))
    tz = db.Column(db.String(120))
    tz_label = db.Column(db.String(120))
    tz_offset = db.Column(db.Integer())
    profile_avatar_hash = db.Column(db.String(120))
    profile_status_text = db.Column(db.String(120))
    profile_status_emoji = db.Column(db.String(120))
    profile_real_name = db.Column(db.String(120))
    profile_display_name = db.Column(db.String(120))
    profile_real_name_normalized = db.Column(db.String(120))
    profile_display_name_normalized = db.Column(db.String(120))
    profile_email = db.Column(db.String(120))
    profile_image_24 = db.Column(db.String(120))
    profile_image_32 = db.Column(db.String(120))
    profile_image_48 = db.Column(db.String(120))
    profile_image_72 = db.Column(db.String(120))
    profile_image_192 = db.Column(db.String(120))
    profile_image_512 = db.Column(db.String(120))
    profile_team = db.Column(db.String(20))
    is_admin = db.Column(db.Boolean())
    is_owner = db.Column(db.Boolean())
    is_primary_owner = db.Column(db.Boolean())
    is_restricted = db.Column(db.Boolean())
    is_ultra_restricted = db.Column(db.Boolean())
    is_bot = db.Column(db.Boolean())
    updated = db.Column(db.Integer())
    is_app_user = db.Column(db.Boolean())
    has_2fa = db.Column(db.Boolean())

    def __repr__(self):
        return '<s-user {}-{}>'.format(self.id, self.name)


class SlackChannel(db.Model):
    id = db.Column(db.String(20), primary_key=True)
    platform_id = db.Column(db.Integer, db.ForeignKey('platform.id'), primary_key=True)
    name = db.Column(db.String(120), index=True)
    is_channel = db.Column(db.Boolean())
    is_group = db.Column(db.Boolean())
    is_im = db.Column(db.Boolean())
    created = db.Column(db.Integer())
    creator = db.Column(db.String(20), index=True)
    is_archived = db.Column(db.Boolean())
    is_general = db.Column(db.Boolean())
    unlinked = db.Column(db.Integer())
    name_normalized = db.Column(db.String(120))
    is_shared = db.Column(db.Boolean())
    is_ext_shared = db.Column(db.Boolean())
    is_org_shared = db.Column(db.Boolean())
    is_pending_ext_shared = db.Column(db.Boolean())
    is_member = db.Column(db.Boolean())
    is_private = db.Column(db.Boolean())
    is_mipm = db.Column(db.Boolean())
    topic = db.Column(db.Text())
    purpose = db.Column(db.Text())
    num_members = db.Column(db.Integer())

    def __repr__(self):
        return '<s-channel {}-{}>'.format(self.id, self.name)


class SlackMessage(db.Model):
    ts = db.Column(db.String(40), primary_key=True)
    type = db.Column(db.String(60))
    slack_user_id = db.Column(db.String(20), db.ForeignKey('slack_user.id'))
    slack_channel_id = db.Column(db.String(20), db.ForeignKey('slack_channel.id'))
    text = db.Column(db.Text())
    is_unread = db.Column(db.Boolean())

    def __repr__(self):
        return '<s-message in {} by {} on {}>'.format(self.slack_channel_id, self.slack_user_id, self.ts)

class GmailMessageLabel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    gmail_message_id = db.Column(db.String(240), db.ForeignKey('gmail_message.id'))
    label = db.Column(db.String(240))
    def __repr__(self):
        return '<g-label {}>'.format(self.label)
    __table_args__ = (db.UniqueConstraint('gmail_message_id', 'label', name='_unique_constraint_gl'),
        )

class GmailMessageText(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    gmail_message_id = db.Column(db.String(240), db.ForeignKey('gmail_message.id'))
    text_hash = db.Column(db.Text())
    text = db.Column(db.UnicodeText())
    is_primary = db.Column(db.Boolean())
    is_multipart = db.Column(db.Boolean())
    is_summary = db.Column(db.Boolean())
    is_snippet = db.Column(db.Boolean())
    multipart_index = db.Column(db.Integer)

    def __repr__(self):
        if bool(self.is_multipart) == True:
            return '<g-message-multipart {}>'.format(self.multipart_index)
        elif self.text:
            return '<g-message-text {}>'.format(self.text[:10].replace('\n', ''))
        else:
            return '<g-message-text {}>'.format(self.gmail_message_id)
    __table_args__ = (db.UniqueConstraint('gmail_message_id', 'text_hash', name='_unique_constraint_gt'),
        )


class GmailMessageListMetadata(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    gmail_message_id = db.Column(db.String(240), db.ForeignKey('gmail_message.id'))
    # what about list/newsletter fields
    list_id = db.Column(db.Text())
    message_id = db.Column(db.Text())
    list_unsubscribe = db.Column(db.Text())
    list_url = db.Column(db.Text())

    def __repr__(self):
        return '<g-message-list mdata {}>'.format(self.list_id)

    __table_args__ = (db.UniqueConstraint('gmail_message_id', 'list_id', name='_unique_constraint_gmlm_list_id'),
        )

class GmailMessageTag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    gmail_message_id = db.Column(db.String(240), db.ForeignKey('gmail_message.id'))
    tag = db.Column(db.String(240))

    def __repr__(self):
        return '<g-tag {}>'.format(self.tag)

    __table_args__ = (db.UniqueConstraint('gmail_message_id', 'tag', name='_unique_constraint_gm_tag'),
        )

class GmailMessage(db.Model):
    id = db.Column(db.String(240), primary_key=True)
    date = db.Column(db.Text())
    from_string = db.Column(db.Text())
    gmail_user_email = db.Column(db.String(240), db.ForeignKey('gmail_user.email'))
    mime_version = db.Column(db.String(10))
    mime_type = db.Column(db.Text())
    content_type = db.Column(db.Text())
    subject = db.Column(db.Text())
    is_multipart = db.Column(db.Boolean())
    multipart_num = db.Column(db.Integer)

    def __repr__(self):
        return '<g-message by {} on {}>'.format(self.from_string, self.date)


class GmailUser(db.Model):
    email = db.Column(db.String(240), primary_key=True)
    platform_id = db.Column(db.Integer, db.ForeignKey('platform.id'), primary_key=True)
    name = db.Column(db.Text())
    is_newsletter = db.Column(db.Boolean())
    type = db.Column(db.String(120))

    def __repr__(self):
        return '<g-user{} with email {}>'.format(self.name, self.email)


class GmailAttachment(db.Model):
    md5 = db.Column(db.Text(), primary_key=True)
    gmail_message_id = db.Column(db.String(240), db.ForeignKey('gmail_message.id'), primary_key=True)
    attachment_id = db.Column(db.Text())
    file_size = db.Column(db.Integer)
    original_filename = db.Column(db.Text())
    part_id = db.Column(db.Text())
    mime_type = db.Column(db.Text())
    file_extension = db.Column(db.Text())
    filepath = db.Column(db.Text())

    def __repr__(self):
        return '<g-attachment with filename {}>'.format(self.original_filename)

class GmailLink(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    gmail_message_id = db.Column(db.String(240), db.ForeignKey('gmail_message.id'))
    link = db.Column(db.Text())
    domain = db.Column(db.Text())

    def __repr__(self):
        return '<g-link {}>'.format(self.id)

    __table_args__ = (db.UniqueConstraint('gmail_message_id', 'link', name='_unique_constraint_gl'),
        )


class SlackAttachment(db.Model):
    md5 = db.Column(db.Text(), primary_key=True)
    slack_message_ts = db.Column(db.String(40), db.ForeignKey('slack_message.ts'), primary_key=True)
    slack_user_id = db.Column(db.String(20))
    size = db.Column(db.Integer)
    created = db.Column(db.Integer)
    timestamp = db.Column(db.Integer)
    id = db.Column(db.String(20))
    filename = db.Column(db.Text())
    filepath = db.Column(db.Text())
    title = db.Column(db.Text())
    mimetype = db.Column(db.Text())
    filetype = db.Column(db.Text())
    pretty_type = db.Column(db.Text())
    user_team = db.Column(db.String(20))
    editable = db.Column(db.Boolean())
    mode = db.Column(db.Text())
    is_external = db.Column(db.Boolean())
    external_type = db.Column(db.Text())
    is_public = db.Column(db.Boolean())
    public_url_shared = db.Column(db.Boolean())
    display_as_bot = db.Column(db.Boolean())
    username = db.Column(db.Text())
    url_private = db.Column(db.Text())
    url_private_download = db.Column(db.Text())
    media_display_type = db.Column(db.Text())
    thumb_pdf = db.Column(db.Text())
    thumb_pdf_w = db.Column(db.Integer)
    thumb_pdf_h = db.Column(db.Integer)
    permalink = db.Column(db.Text())
    permalink_public = db.Column(db.Text())
    is_starred = db.Column(db.Boolean())
    has_rich_preview = db.Column(db.Boolean())
    file_access = db.Column(db.Text())

    def __repr__(self):
        return '<s-attachment with filename {}>'.format(self.filename)

class SlackLink(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    slack_message_ts = db.Column(db.String(40), db.ForeignKey('slack_message.ts'))
    has_text = db.Column(db.Text())
    url = db.Column(db.Text())
    text = db.Column(db.UnicodeText())
    domain = db.Column(db.Text())
    content = db.Column(db.Text())

    def __repr__(self):
        return '<s-link with domain {}>'.format(self.domain)


    __table_args__ = (db.UniqueConstraint('slack_message_ts', 'url', name='_unique_constraint_su'),
        )

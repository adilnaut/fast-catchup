from app import db
from sqlalchemy import func, union
from flask_login import UserMixin
from app import login
from sqlalchemy import select
import sqlalchemy as sa
from werkzeug.security import generate_password_hash, check_password_hash
from sklearn.neighbors import NearestNeighbors
from sentence_transformers import SentenceTransformer
import numpy as np
import importlib
import pickle

@login.user_loader
def load_user(id):
    return User.query.get(int(id))

# ideally we not only want columns list but
# list of implemented equality functions
# or similarity score calculators
# here column order is very important
# that would decide sampling bias
# first element of columns_list is TableName id id_column
def smart_filtering(TableName, columns_list, m_item, query, max_samples=10, min_samples=2):
    # initial number of rows
    _ = query.all()
    if len(_) <= max_samples:
        return _
    # todo
    # TableName is message table
    # where query have query of PriorityItem elements
    result_query = None
    for column_name in columns_list[1:]:
        # print(column_name)
        if '.' in column_name:
            meta_table, meta_column = column_name.split('.')
            # MetaTable = getattr(models, meta_table)
            MetaTable = globals()[meta_table]
            # todo
            # here we should get MetaTable instance of m_item
            # and also query and filter item results to pass through

            m_item_meta = MetaTable.query.join(TableName) \
                .filter(getattr(TableName, columns_list[0]) == getattr(m_item, columns_list[0])).all()
            # just query results list for each m_item_meta instance and do something with list of outputs
            results_list = []

            # now we have 0 or more instances of item meta and list of metas of priority_messages
            # probably have to group by PriorityItem which is originally selected
            # should we take union of all the queries, but without repitions in values?
            i = 0
            for m_meta in m_item_meta:
                # assume that explicit foreign key definition handles join params
                result_query = query.join(PriorityMessage) \
                    .join(TableName, getattr(TableName, columns_list[0]) == PriorityMessage.message_id) \
                    .join(MetaTable) \
                    .filter(getattr(MetaTable, meta_column) == getattr(MetaTable, meta_column))
                # result = result_query.all()
                results_list.append(result_query)
                i += 1
            result_query = union(*results_list)
            # result_query = union(results_list[0], results_list[1])
            # print(result_query)
            # result = result_query
            # result_query = result_query.select()
            result = db.session.execute(result_query).fetchall()
            # result = result.all()
            result = cast_tuples_to_p_items(result)
        else:
            result_query = query.join(PriorityMessage) \
                .join(TableName, getattr(TableName, columns_list[0]) == PriorityMessage.message_id) \
                .filter(getattr(TableName, column_name) == getattr(m_item, column_name))
            result = result_query.all()
        if len(result) <= min_samples:
            return _
        if len(result) <= max_samples:
            return result
    return result

def cast_tuples_to_p_items(rows):
    stmts = [
        sa.select(
            sa.cast(sa.literal(i), sa.Integer).label('id'),
            sa.cast(sa.literal(s), sa.Float).label('score'),
            sa.cast(sa.literal(pli), sa.Integer).label('priority_list_id'),
            sa.cast(sa.literal(pmi), sa.Integer).label('priority_message_id'),
            sa.cast(sa.literal(pb), sa.Float).label('p_b'),
            sa.cast(sa.literal(pba), sa.Float).label('p_b_a'),
            sa.cast(sa.literal(pab), sa.Float).label('p_a_b'),
            sa.cast(sa.literal(pa), sa.Float).label('p_a'),
            sa.cast(sa.literal(pac), sa.Float).label('p_a_c'),
            sa.cast(sa.literal(pbc), sa.Float).label('p_b_c'),
            sa.cast(sa.literal(pabc), sa.Float).label('p_a_b_c'))
            for idx, (i, s, pli, pmi, pb, pba, pab, pa, pac, pbc, pabc) in enumerate(rows)
    ]
    subquery = sa.union_all(*stmts)
    subquery = subquery.alias(name="temp_priority_items")
    query = (
        db.session
        .query(PriorityItem)
        .join(subquery, subquery.c.id == PriorityItem.id)
        # .filter(subquery.c.date >= XXX_DATE)
    )
    return query.all()


class PriorityList(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Text())
    platform_id = db.Column(db.Integer, db.ForeignKey('platform.id'))
    created = db.Column(db.Integer)
    p_a = db.Column(db.Float())
    items = db.relationship('PriorityItem', backref='list', lazy='dynamic')

    def update_p_a(self):
        items = db.session.query(PriorityItem) \
            .join(PriorityList) \
            .filter(PriorityList.platform_id == self.platform_id) \
            .filter(PriorityList.id != self.id) \
            .all()
        # average real importance of message
        p_as = []
        for item in items:
            if item.p_a:
                p_as.append(item.p_a)
        self.p_a = np.array(p_as).mean() if p_as else 0.3
        db.session.commit()

    __table_args__ = (db.UniqueConstraint('session_id', 'platform_id', name='_unique_constraint_sess_plat'),
        )

class PriorityListMethod(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    platform_id = db.Column(db.Integer, db.ForeignKey('platform.id'))
    p_m_a = db.Column(db.Float())
    name = db.Column(db.Text())
    python_path = db.Column(db.Text())

    def update_p_m_a(self, plist_id):
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
        platform_id = self.platform_id
        p_lists = PriorityList.query.filter_by(platform_id=platform_id) \
            .filter(PriorityList.id != plist_id) \
            .all()
        result = []
        for p_list in p_lists:
            # p_methods = PriorityListMethod.query.filter_by(priority_list_id=p_list.id).all()
            p_items = PriorityItem.query.filter_by(priority_list_id=p_list.id).all()
            for p_item in p_items:
                p_item_method = PriorityItemMethod.query \
                    .filter_by(priority_item_id=p_item.id) \
                    .filter_by(priority_list_method_id=self.id) \
                    .first()
                if p_item.p_b_a and p_item_method and p_item_method.p_b_m_a and p_item.p_a:
                    weighted_accuracy = abs(p_item_method.p_b_m_a - p_item.p_b_a) * p_item.p_a
                    result.append(weighted_accuracy)
        self.p_m_a = np.array(result).mean() if result else 0.05
        db.session.commit()


    __table_args__ = (db.UniqueConstraint('platform_id', 'name', name='_unique_constraint_plat_name'),
        )


class PriorityItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    score = db.Column(db.Float())
    priority_list_id = db.Column(db.Integer, db.ForeignKey('priority_list.id'))
    priority_message_id = db.Column(db.Integer, db.ForeignKey('priority_message.id'))
    p_b = db.Column(db.Float())
    p_b_a = db.Column(db.Float())
    p_a_b = db.Column(db.Float())
    p_a = db.Column(db.Float())
    methods = db.relationship('PriorityItemMethod', backref='item', lazy='dynamic')
    p_a_c = db.Column(db.Float())
    p_b_c = db.Column(db.Float())
    p_a_b_c = db.Column(db.Float())

    def calculate_p_a_c(self, TableName, columns_list):
        m_item = TableName.query \
            .join(PriorityMessage, getattr(TableName, columns_list[0]) == PriorityMessage.message_id) \
            .filter(PriorityMessage.id == self.priority_message_id).first()

        result = PriorityList.query.filter_by(id=self.priority_list_id).first()
        platform_id = result.platform_id

        items_query = db.session.query(PriorityItem) \
            .join(PriorityList) \
            .filter(PriorityList.platform_id == platform_id) \
            .filter(PriorityList.id != self.id)

        items = smart_filtering(TableName, columns_list, m_item, items_query)
        # average real importance of message
        p_as = []
        for item in items:
            if item.p_a:
                p_as.append(item.p_a)
        self.p_a_c = np.array(p_as).mean() if p_as else 0.3
        db.session.commit()

    # expensive, we build knn model for each item
    def calculate_p_b_c(self, TableName, columns_list):
        # ideally we should have 10 nearest neighbors classifiers object fitted on all previous data
        # but for now we can train it right there
        result = PriorityList.query.filter_by(id=self.priority_list_id).first()
        platform_id = result.platform_id

        p_items_query = PriorityItem.query.join(PriorityList) \
            .filter(PriorityList.platform_id == platform_id) \
            .filter(PriorityList.id != self.priority_list_id)

        m_item = TableName.query \
            .join(PriorityMessage, getattr(TableName, columns_list[0]) == PriorityMessage.message_id) \
            .filter(PriorityMessage.id == self.priority_message_id).first()

        p_items = smart_filtering(TableName, columns_list, m_item, p_items_query)

        ids = []
        all_vectors = []
        nbrs = None

        for p_item in p_items:
            # p_methods = PriorityListMethod.query.filter_by(priority_list_id=p_list.id).all()
            _ = PriorityMessage.query.filter_by(id=p_item.priority_message_id).first()
            ids.append(_.id)
            # emb_vector = struct.unpack('<q', b'\x15\x00\x00\x00\x00\x00\x00\x00')
            emb_vector = np.frombuffer(_.embedding_vector, dtype='<f4')
            all_vectors.append(emb_vector)

        if all_vectors:
            X = np.array(all_vectors)
            # we want to build NN algorithm for any number of samples present
            # but initially there would not be many
            # let's set this up to 2 for now
            nbrs = NearestNeighbors(n_neighbors=2, algorithm='ball_tree').fit(X)

        p_m_result = PriorityMessage.query.filter_by(id=self.priority_message_id).first()
        p_m_vector = p_m_result.embedding_vector
        p_m_vector = np.frombuffer(p_m_vector, dtype='<f4')
        p_m_vector = np.array([p_m_vector])


        if nbrs:
            distances, indices = nbrs.kneighbors(p_m_vector)
            p_as = []
            indices = indices[0]
            for n_i in indices:
                n_id = ids[n_i]
                n_item = PriorityItem.query.filter_by(priority_message_id=n_id).one()
                if n_item and n_item.p_a:
                    p_as.append(n_item.p_a)
            self.p_b_c = np.array(p_as).mean()
        else:
            self.p_b_c = 0.2
        db.session.commit()

    def calculate_p_b(self, nbrs, ids):
        # get priority_message vector
    	# get first k neighbors sample
    	# get number of important ones
    	# and divide by k

        # this is numpy array with either ChatGPT embedding, w2v embedding or sklearn bag of words
        p_m_result = PriorityMessage.query.filter_by(id=self.priority_message_id).first()
        p_m_vector = p_m_result.embedding_vector
        p_m_vector = np.frombuffer(p_m_vector, dtype='<f4')
        p_m_vector = np.array([p_m_vector])


        if nbrs:
            distances, indices = nbrs.kneighbors(p_m_vector)
            p_as = []
            indices = indices[0]
            for n_i in indices:
                n_id = ids[n_i]
                n_item = PriorityItem.query.filter_by(priority_message_id=n_id).one()
                if n_item and n_item.p_a:
                    p_as.append(n_item.p_a)
            self.p_b = np.array(p_as).mean()
        else:
            self.p_b = 0.2
        db.session.commit()

    def calculate_p_b_a(self):
        # get all priority_item methods and sum over
	    # assert p_m_a of all methods sum is one
        p_item_methods = PriorityItemMethod.query.filter_by(priority_item_id=self.id).all()
        sum = 0
        for p_item_method in p_item_methods:
            p_list_method = PriorityListMethod.query.filter_by(id=p_item_method.priority_list_method_id).one()
            p_m_a = p_list_method.p_m_a
            p_b_m_a = p_item_method.p_b_m_a
            if p_m_a and p_b_m_a:
                sum += p_b_m_a * p_m_a
        self.p_b_a = sum
        db.session.commit()


    def calculate_p_a_b(self):
        # call calculte_p_b_a
	    # call calculate_p_b
	    # p_a_b = p_b_a * p_a / p_b
        p_a = PriorityList.query.filter_by(id=self.priority_list_id).first().p_a
        # print(p_a)
        # print(self.p_b)
        # print(self.p_b_a)
        if self.p_b_a and p_a and self.p_b:
            self.p_a_b = self.p_b_a * p_a / self.p_b
        else:
            self.p_a_b = 0.497424242
        db.session.commit()

    def calculate_p_a_b_c(self):

        if self.p_b_a and self.p_a_c and self.p_b_c:
            self.p_a_b_c = self.p_b_a * self.p_a_c / self.p_b_c
        else:
            self.p_a_b_c = 0.49696969
        db.session.commit()

    __table_args__ = (db.UniqueConstraint('priority_list_id', 'priority_message_id', name='_unique_constraint_pl_pm'),
        )

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
        priority_item = PriorityItem.query.filter_by(id=self.priority_item_id).one()
        priority_message = PriorityMessage.query.filter_by(id=priority_item.priority_message_id).one()
        inp_text = priority_message.input_text_value
        priority_list_method = PriorityListMethod.query.filter_by(id=self.priority_list_method_id).one()
        python_path = priority_list_method.python_path
        name = priority_list_method.name
        # how would python_path look like?
        #  python_path 'quickstart\priority_method.py'
        #  name 'ask_gpt'
        # todo:
        # check if python_path exists
        # check that attribute exists
        package_name, module_name = python_path.split('.')
        script_module = importlib.import_module('.%s' % module_name, package=package_name)
        method_function = getattr(script_module, name)
        self.p_b_m_a = method_function(inp_text)
        db.session.commit()

    __table_args__ = (db.UniqueConstraint('priority_item_id', 'priority_list_method_id', name='_unique_constraint_pitem_plmethod'),
        )

class PriorityMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # implicit foreign key at this stage
    platform_id = db.Column(db.Integer, db.ForeignKey('platform.id'))
    session_id = db.Column(db.Text())
    message_id = db.Column(db.Integer)
    input_text_value = db.Column(db.Text())
    embedding_vector = db.Column(db.LargeBinary)

    def enrich_input_text_value(self, inp_text):
        self.input_text_value = inp_text
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
    __table_args__ = (db.UniqueConstraint('session_id', 'message_id', name='_unique_constraint_sess_mess'),
        )

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
    platforms = db.relationship('Platform', backref='workspace', lazy='dynamic')

    def __repr__(self):
        return '<workspace {}>'.format(self.id)

class Platform(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text())
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspace.id'))
    auth_method = db.Column(db.Text())
    auth_records = db.relationship('AuthData', backref='platform', lazy='dynamic')
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
    session_id = db.Column(db.Text())
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
    session_id = db.Column(db.Text())

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

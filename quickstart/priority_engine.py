import numpy as np

from collections import OrderedDict
from datetime import datetime

from quickstart.sqlite_utils import get_insert_query

def build_knn(PriorityList, PriorityItem, PriorityMessage, p_item):
    # ideally we should have 10 nearest neighbors classifiers object fitted on all previous data
    # but for now we can train it right there
    result = PriorityList.query.filter_by(id=p_item.priority_list_id).first()
    platform_id = result.platform_id
    # get all priority_list items except a fresh one
    p_lists = PriorityList.query.filter_by(platform_id=platform_id) \
        .filter(PriorityList.id != p_item.priority_list_id) \
        .all()
    ids = []
    all_vectors = []
    for p_list in p_lists:
        # p_methods = PriorityListMethod.query.filter_by(priority_list_id=p_list.id).all()
        p_items = PriorityItem.query.filter_by(priority_list_id=p_list.id).all()
        for p_item in p_items:
            _ = PriorityMessage.query.filter_by(id=p_item.priority_message_id).one()
            ids.append(_.id)
            all_vectors.append(_.embedding_vector)
    if all_vectors:
        X = np.array(all_vectors)
        nbrs = NearestNeighbors(n_neighbors=10, algorithm='ball_tree').fit(X)
    return nbrs, ids

def create_priority_list(db, PriorityList, platform_id, session_id):

    timestamp = int(round(datetime.now().timestamp()))
    plist_kwargs = OrderedDict([('session_id', session_id)
        , ('platform_id', platform_id)
        , ('created', timestamp)
        ])
    plist_query = get_insert_query('priority_list', plist_kwargs.keys())
    db.session.execute(plist_query, plist_kwargs)
    db.session.commit()

    p_list = PriorityList.query.filter_by(session_id=session_id) \
        .filter_by(platform_id=platform_id) \
        .one()
    p_list.update_p_a()
    return p_list.id


def create_priority_list_methods(db, PriorityListMethod, platform_id):
    script_path = os.path.join('quickstart', 'priority_method.py')
    methods = [(script_path, 'ask_gpt')
        , (script_path, 'toy_keyword_match')
        , (script_path, 'sentiment_analysis')]

    for python_path, name in methods:
        plist_method_kwargs = OrderedDicts([('platform_id', platform_id)
            , ('name', name)
            , ('python_path', python_path)])
        plist_method_query = get_insert_query('priority_list_method', plist_method_kwargs.keys())
        db.session.execute()
        db.session.commit()

        pl_method = PriorityListMethod.query.filter_by(platform_id=platform_id) \
            .filter_by(name=name) \
            .one()
        pl_method.update_p_m_a()

def update_priority_list_methods(db, PriorityListMethod, platform_id):
    pl_methods = PriorityListMethod.query.filter_by(platform_id=platform_id).all()
    for pl_method in pl_methods:
        pl_method.update_p_m_a()

# todo: replace with named tuple
def fill_priority_list(db, messages, get_abstract_func, plist_id, \
        PriorityMessage, PriorityList, PriorityItem, PriorityItemMethod, PriorityListMethod):
    # iterate over records of variable platform
    message_ids = []
    item_ids = []
    result = PriorityList.query.filter_by(id=p_item.priority_list_id).first()
    platform_id = result.platform_id
    method_ids = [ x.id for x in PriorityListMethod.query.filter_by(platform_id=platform_id).all() ]
    method_item_ids = []

    for message in messages:
        inp_text, m_id = get_abstract_func(message)
        p_message_kwargs = OrderedDict([('message_id', m_id)
            , ('input_text_value', inp_text)])
        p_message_query = get_insert_query('priority_message', p_message_kwargs.keys(), returning_id=True)
        result = db.session.execute(p_message_query, p_message_kwargs).one()
        message_id = result.id
        message_ids.append(message_id)
    db.session.commit()


    priority_messages = db.session.query(PriorityMessage) \
        .filter(PriorityMessage.id.in_(tuple(message_ids))) \
        .all()
    sentences = [x.input_text_value for x in priority_messages]
    model_filepath = os.path.join('file_store', '2023-02-22-embedding-model')
    model_pickle = open(model_filepath, 'rb')
    embedding_model = pickle.load(model_pickle)
    embedding_vectors = embedding_model.encode(sentences)
    assert len(embedding_vectors) == len(priority_messages)
    # todo: assert items correspond appropriately, not only by length of arrays but elementwise assertion
    for i in range(len(priority_messages)):
        priority_message[i].embedding_vector = embedding_vector[i]
    db.session.commit()

    for message_id in message_ids:
        p_item_kwargs = OrderedDict([('priority_list_id', plist_id)
            , ('priority_message_id', message_id)])
        p_item_query = get_insert_query('priority_ite', p_item_kwargs.keys(), returning_id=True)
        result = db.session.execute(p_item_query, p_item_kwargs).one()
        item_id = result.id
        item_ids.append(item_id)
    db.session.commit()

    for item_id in item_ids:
        for method_id in method_ids:
            pi_method_kwargs = OrderedDict([('priority_item_id', item_id)
                , ('priority_list_method_id', method_id)])
            pi_method_query = get_insert_query('priority_item_method', pi_method_kwargs.keys(), returning_id=True)
            result = db.session.execute(pi_method_query, pi_method_kwargs)
            method_item_id = result.id
            method_item_ids.append(method_item_id)
    db.session.commit()

    # todo there is also an obvious optimisation opportunity
    #  chat could also do priority estimation based on text in bulk
    #  however that might degrade accuracy or make ouput unpredictable
    priority_method_items = db.session.query(PriorityItemMethod) \
        .filter(PriorityItemMethod.id.in_(tuple(method_item_ids))) \
        .all()

    for priority_method_item in priority_method_items:
        priority_method_item.calculate_p_b_m_a()

    # todo optimise calculate_p_b cause it build the same KNearestNeighbors model each item
    priority_items = db.session.query(PriorityItem).filter(PriorityItem.id.in_(tuple(item_ids))).all()
    for priority_item in priority_items:
        nbrs, ids = build_knn(PriorityList, PriorityItem, PriorityMessage, priority_item)
        priority_item.calculate_p_b(nbrs, ids)
        priority_item.calculate_p_b_a()
        priority_item.calculate_p_a_b()

from sqlalchemy.sql import text

# todo: prime_keys should be a string of prime_keys in the same order as in columns separated by comma and one whitespace
def get_upsert_query(table_name, columns, prime_keys):
    gen_upsert = '''INSERT INTO {table_name} ({columns_list})
        VALUES({params_list})
        ON CONFLICT({prime_keys})
        DO UPDATE SET {excluded_list};'''

    def excl(x):
        return '{0}=excluded.{0}'.format(x)


    upsert_dict = {'table_name': table_name
        , 'columns_list': ', '.join(columns)
        , 'params_list': ', '.join([':%s' % x for x in columns])
        , 'prime_keys': prime_keys
        , 'excluded_list': ', '.join([excl(x) for x in columns if x not in prime_keys])
    }

    upsert_query = gen_upsert.format(**upsert_dict)
    return text(upsert_query)

def get_insert_query(table_name, columns, returning_id=False):
    gen_insert = '''INSERT OR IGNORE INTO {table_name} ({columns_list})
        VALUES({params_list})'''
    if returning_id:
        gen_insert += 'RETURNING id'
    gen_insert += ';'


    insert_dict = {'table_name': table_name
        , 'columns_list': ', '.join(columns)
        , 'params_list': ', '.join([':%s' % x for x in columns])
    }

    insert_query = gen_insert.format(**insert_dict)
    return text(insert_query)

import psycopg2
import re
import itertools
import json

def default_max_db_connections(db_url):
    conn = psycopg2.connect(dsn=db_url)
    with conn.cursor() as cur:
            cur.execute("SELECT greatest(1, ((SELECT setting::int FROM pg_settings WHERE name='max_connections')-(SELECT count(*) FROM pg_stat_activity) - 4)::int)")
            num_connections = cur.fetchone() 
    conn.close()
    return num_connections[0]

def get_select_fields(select):
    return "*" if len(select) == 0 else ",".join(select)
    
translated_queries = {}
def translate_to_pyformat(query_string, params):
    """
    Translates dollar sign number parameters and list parameters to pyformat strings.

    Args:
        query_string (str): The query string with parameters.
        params (list): List of parameter values.

    Returns:
        str: The query string with translated pyformat parameters.
        dict: A dictionary mapping parameter numbers to their values.
    """

    translated_params = {}
    if params != None:
        for idx, param in enumerate(params):
            translated_params[str(idx+1)] = param

    if query_string in translated_queries:
        return translated_queries[query_string], translated_params

    dollar_params = re.findall(r'\$[0-9]+', query_string)
    translated_string = query_string
    for dollar_param in dollar_params:
        # Extract the number after the $
        param_number = int(dollar_param[1:])
        if params != None:
            pyformat_param = '%s' if param_number == 0 else f'%({param_number})s'
        else:
            pyformat_param = '%s'
        translated_string = translated_string.replace(
            dollar_param, pyformat_param)

    translated_queries[query_string] = translated_string
    return translated_queries[query_string], translated_params

def norm(distance, distance_type):
    if distance_type == 'cosine':
        return 1-max(distance, 0.0)
    return distance

class dotdict(dict):
    """dot.notation access to dictionary attributes"""
    __getattr__ = dict.get
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__

def chunks(iterable, batch_size=100):
    it = iter(iterable)
    chunk = tuple(itertools.islice(it, batch_size))
    while chunk:
        yield chunk
        chunk = tuple(itertools.islice(it, batch_size))

def index_of(l, s):
     try:
        return l.index(s)
     except ValueError:
        return -1

def get_vector_result(rows=[], select_fields=[], first=False):
    id_idx = -1
    embedding_idx = -1
    metadata_idx = -1
    
    if len(rows) == 0:
        return []

    if len(select_fields) == 0:
        id_idx = 0
        metadata_idx = 1
        embedding_idx = 2
    else:
        id_idx = index_of(select_fields, "id")
        embedding_idx = index_of(select_fields, "embedding")
        metadata_idx = index_of(select_fields, "metadata")
    
    results = []

    for data in rows:
        result_vec = { "id": None, "embedding": None, "metadata": None, "distance": -1 }

        if id_idx > -1:
            result_vec["id"] = data[id_idx]
        if embedding_idx > -1:
            result_vec["embedding"] = data[embedding_idx]
        if metadata_idx > -1:
            result_vec["metadata"] = None if data[metadata_idx] is None else dotdict(data[metadata_idx])

        result_vec["distance"] = data[len(data) - 1]

        results.append(dotdict(result_vec))

    if first:
        return None if len(results) == 0 else results[0]

    return results

def prepare_insert_data(row):
    id = row[0]
    vec = row[1]
    metadata = 'null' if len(row) < 3 else row[2]

    if type(metadata) != str:
        metadata = json.dumps(metadata)

    return (id, vec, metadata)

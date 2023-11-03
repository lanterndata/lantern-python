import psycopg2
import re

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

# Upload the sample data formatted as (id, vector) tuples.
import itertools

def chunks(iterable, batch_size=100):
    it = iter(iterable)
    chunk = tuple(itertools.islice(it, batch_size))
    while chunk:
        yield chunk
        chunk = tuple(itertools.islice(it, batch_size))

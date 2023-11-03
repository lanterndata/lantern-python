from contextlib import contextmanager
import json
import psycopg2.pool
from lantern_client import QueryBuilder, SyncClient 
from utils import chunks, default_max_db_connections, dotdict, norm, translate_to_pyformat

global_pool = None
indexes_table_name = "lantern_indexes"

class IndexStatusReady():
    def __init__(self ):
        self.status = { "ready": True }

class Index():
    def __init__(self, index_name: str, pool=None, dimensions: int = 3, metric: str = "euclidean") -> None:
        self.pool = pool or global_pool
        self.name = index_name
        self.namespace_clients = {}
        self.namespace_table_name = QueryBuilder._quote_ident(f"{self.name}_namespaces")

        info = self._get_index_info()
        if info is None:
            raise(Exception(f"Index {self.name} does not exist"))
        
        self.dimensions = info['dimensions']
        self.metric = info['metric']
        for namespace in self._get_namespaces():
            self.namespace_clients[namespace] = SyncClient(pool=self.pool, table_name=f"{self.name}_{namespace}", dimensions=dimensions, distance_type=metric)

    @contextmanager
    def _connect(self):
        connection = self.pool.getconn()
        try:
            yield connection
            connection.commit()
        finally:
            self.pool.putconn(connection)

    def _get_index_info(self):
        with self._connect() as conn:
            with conn.cursor() as cur:
                query, params = translate_to_pyformat("SELECT metric, dim FROM {table_name} WHERE name=$1 LIMIT 1".format(table_name=indexes_table_name), (self.name, ))
                cur.execute(query, params)
                rows = cur.fetchall()
                if len(rows) == 0:
                    return None

                row = rows[0]
                return {"metric": row[0], "dimensions": row[1]}
        
    def _add_namespace(self, namespace):
        client = SyncClient(pool=self.pool, table_name=f"{self.name}_{namespace}", dimensions=self.dimensions, distance_type=self.metric)

        with self._connect() as conn:
            with conn.cursor() as cur:
                query, params = translate_to_pyformat("INSERT INTO {table_name} (name) VALUES ($1)".format(table_name=self.namespace_table_name), (namespace,))
                cur.execute(query, params)

        client.create_table()
        client.create_index()
        self.namespace_clients[namespace] = client

        return client


    def _get_namespaces(self):
         with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT name FROM {table_name}".format(table_name=self.namespace_table_name))
                return list(map(lambda x: x[0], cur.fetchall()))

    def _init_index(self):
        for client in self.namespace_clients.values():
            client.create_table()
            client.create_index()

    def _get_client(self, namespace=''):
        client = self.namespace_clients.get(namespace)

        if client is None:
            return self._add_namespace(namespace)
        return client

    def upsert(self, vectors, copy=False, namespace=''):
        values = []
        for data in vectors:
            if type(data) is dict:
                id = data.get('id')
                metadata = data.get('metadata')
                vec = data.get('values')
            else:
                id = data[0]
                vec = data[1]
                metadata = None

                if len(data) > 2:
                    metadata = data[2]
            
            if type(vec) is not list:
                vec = list(vec)

            values.append((id, json.dumps(metadata), vec))

        if copy:
            self._get_client(namespace).bulk_insert(values)
        else:
            self._get_client(namespace).upsert(values)
        return len(values)

    def delete(self, ids, namespace = ''):
        self._get_client(namespace).delete_by_ids(ids)
 
    def fetch(self, ids, namespace = ''):
        results = self._get_client(namespace).get_by_ids(ids, ['id', 'metadata', 'embedding'])
        vectors = {}

        for data in results:
            id = data[0]
            metadata = data[1]
            values = data[2]
            vectors[id] = { "id": id, "metadata": metadata or {}, "values": values }
           
        return { "namespace": namespace, "vectors": vectors }

    def query(self, vector=None, top_k=10, namespace = '', include_values=False, include_metadata=False, id=None, filter=None):
        select_fields = ['id']
        meta_idx = -1
        emb_idx = -1

        if include_values:
            select_fields.append('embedding')
            emb_idx = 1
            
        if include_metadata:
            select_fields.append('metadata')
            meta_idx = select_fields.index('metadata')
        
        data = self._get_client(namespace).search(id, vector, top_k, filter, select_fields)
        matches = list(map(lambda x: dotdict({ "id": x[0], "score": norm(x[len(x) - 1], self.metric), "values": [] if emb_idx == -1 else x[emb_idx], "metadata": {} if meta_idx == -1 else dotdict(x[meta_idx]) }), data))
        return dotdict({ "namespace": namespace, "matches": matches })
        
    def update(self, id, values = None, set_metadata = None, namespace = ''):
        pass

    def describe_index_stats(self):
        total_count = 0
        namespaces = {}
        for key, client in self.namespace_clients.items():
            namespace_count = client.count()
            namespaces[key] = { 'vector_count': namespace_count }
            total_count += namespace_count

        return dotdict({ "dimensions": self.dimensions, "index_fullness": 1.0, "total_count": total_count, "namespaces": namespaces})

    def describe(self):
        return dotdict({"status" : { "ready": True }})

    def _drop(self):
        for client in self.namespace_clients.values():
            client.drop()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("DROP TABLE {table_name} CASCADE".format(table_name=self.namespace_table_name))
                query, params = translate_to_pyformat("DELETE FROM {table_name} WHERE name=$1".format(table_name=indexes_table_name), (self.name, ))
                cur.execute(query, params)


class GRPCIndex(Index):
    def upsert_from_dataframe(self, dataset,batch_size=1000, copy=False, namespace=''):
        if copy:
            self.upsert(dataset.values.tolist(), copy=True, namespace=namespace)
        else:
            for chunk in chunks(dataset.values.tolist(), batch_size):
                self.upsert(chunk, namespace=namespace)
    pass
# Exported functions
def init(url: str):
    connect(url)
    
def connect(db_url):
    global global_pool
    max_db_connections = default_max_db_connections(db_url)

    global_pool = psycopg2.pool.SimpleConnectionPool(
        1, max_db_connections, dsn=db_url)
    
    conn = global_pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute("CREATE TABLE IF NOT EXISTS {table_name} (id SERIAL PRIMARY KEY, name TEXT, metric TEXT, dim INT)".format(table_name=indexes_table_name))
        conn.commit()
    finally:
            global_pool.putconn(conn)
        
def create_index(name, dimension, metric):
    namespace_table_name = QueryBuilder._quote_ident(f"{name}_namespaces")
    conn = global_pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute("CREATE TABLE IF NOT EXISTS {table_name} (id SERIAL PRIMARY KEY, name TEXT UNIQUE)".format(table_name=namespace_table_name))
            cur.execute("INSERT INTO {table_name} (name) VALUES ('')".format(table_name=namespace_table_name))
            query, params = translate_to_pyformat("INSERT INTO {table_name} (name, metric, dim) VALUES ($1,$2,$3)".format(table_name=indexes_table_name),(name, metric, dimension))
            cur.execute(query, params)
        conn.commit()
    finally:
            global_pool.putconn(conn)
    index = Index(pool=global_pool, index_name=name, dimensions=dimension, metric=metric)
    index._init_index()
    return index

def delete_index(name):
    return Index(pool=global_pool, index_name=name)._drop()

def list_indexes():
    conn = global_pool.getconn()
    indexes = []
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT name FROM {table_name}".format(table_name=indexes_table_name));
            indexes = list(map(lambda x: x[0], cur.fetchall()))
    finally:
            global_pool.putconn(conn)
    return indexes

def describe_index(index_name: str):
    return Index(pool=global_pool, index_name=index_name).describe()
    


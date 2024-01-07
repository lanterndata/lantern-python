import json
import os
import math
import threading
import psycopg2.pool
import pinecone
from contextlib import contextmanager
from typing import List, Optional
from pinecone.core.client.model.vector import Vector
from tqdm import tqdm
from lantern import QueryBuilder, SyncClient 
from lantern.utils import chunks, default_max_db_connections, dotdict, norm, translate_to_pyformat

global_pool = None
indexes_table_name = "lantern_indexes"

class IndexStatusReady():
    def __init__(self ):
        self.status = { "ready": True }

class Index():
    def __init__(self, index_name: str, ef=None, pool=None) -> None:
        self.pool = pool or global_pool
        self.name = index_name
        self.namespace_clients = {}
        self.namespace_table_name = QueryBuilder._quote_ident(f"{self.name}_namespaces")

        info = self._get_index_info()
        if info is None:
            raise(Exception(f"Index {self.name} does not exist"))
        
        self.dimensions = info['dimensions']
        self.metric = info['metric']
        self.m = info['m']
        self.ef = ef or info['ef']
        self.ef_construction = info['ef_construction']
        for namespace in self._get_namespaces():
            table_name = self.name if namespace == "" else f"{self.name}_{namespace}"
            self.namespace_clients[namespace] = SyncClient(pool=self.pool, table_name=table_name, dimensions=self.dimensions, distance_type=self.metric, m=self.m, ef=self.ef, ef_construction=self.ef_construction)

    @contextmanager
    def _connect(self):
        if self.pool is None:
            raise(Exception("Client is not initialized"))

        connection = self.pool.getconn()
        try:
            yield connection
            connection.commit()
        finally:
            self.pool.putconn(connection)

    def _get_index_info(self):
        with self._connect() as conn:
            with conn.cursor() as cur:
                query, params = translate_to_pyformat("SELECT metric, dim, m, ef, ef_construction FROM {table_name} WHERE name=$1 LIMIT 1".format(table_name=indexes_table_name), (self.name, ))
                cur.execute(query, params)
                rows = cur.fetchall()
                if len(rows) == 0:
                    return None

                row = rows[0]
                return {"metric": row[0], "dimensions": row[1], "m": row[2], "ef": row[3], "ef_construction": row[4] }
        
    def _add_namespace(self, namespace):
        client = SyncClient(pool=self.pool, table_name=f"{self.name}_{namespace}", dimensions=self.dimensions, distance_type=self.metric)

        with self._connect() as conn:
            with conn.cursor() as cur:
                query, params = translate_to_pyformat("INSERT INTO {table_name} (name) VALUES ($1)".format(table_name=self.namespace_table_name), (namespace,))
                cur.execute(query, params)

        client.create_table()
        self.namespace_clients[namespace] = client

        return client


    def _get_namespaces(self):
         with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT name FROM {table_name}".format(table_name=self.namespace_table_name))
                return list(map(lambda x: x[0], cur.fetchall()))

    def _init_index_tables(self):
        for client in self.namespace_clients.values():
            client.create_table()

    def _init_index_indices(self):
        for client in self.namespace_clients.values():
            client.create_index()
            
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
            elif isinstance(data, Vector):
                id = data.id
                metadata = data.metadata
                vec = data.values
            else:
                id = data[0]
                vec = data[1]
                metadata = None

                if len(data) > 2:
                    metadata = data[2]
            
            if type(vec) is not list:
                vec = list(vec)

            values.append((id, vec, json.dumps(metadata)))

        if copy:
            self._get_client(namespace).bulk_insert(values)
        else:
            self._get_client(namespace).upsert_many(values)
        return len(values)

    def delete(self, ids, namespace = ''):
        self._get_client(namespace).delete_by_ids(ids)
 
    def fetch(self, ids, namespace = ''):
        results = self._get_client(namespace).get_by_ids(ids, ['id', 'metadata', 'embedding'])
        vectors = {}

        for vector in results:
            vectors[vector.id] = vector
           
        return { "namespace": namespace, "vectors": vectors }

    def query(self, vector=None, top_k=10, namespace = '', include_values=False, include_metadata=False, id=None, filter=None):
        select_fields = ['id']

        if include_values:
            select_fields.append("embedding")
        if include_metadata:
            select_fields.append("metadata")

        data = self._get_client(namespace).search(id, vector, top_k, filter, select_fields)
        matches = list(map(lambda x: dotdict({ "id": x.id, "score": norm(x.distance, self.metric), "values": x.embedding, "metadata": x.metadata }), data))
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
                cur.execute("DROP TABLE IF EXISTS {table_name} CASCADE".format(table_name=self.namespace_table_name))
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
            cur.execute("CREATE TABLE IF NOT EXISTS {table_name} (id SERIAL PRIMARY KEY, name TEXT, metric TEXT, dim INT, m INT, ef INT, ef_construction INT)".format(table_name=indexes_table_name))
        conn.commit()
    finally:
            global_pool.putconn(conn)
        
def create_index(name, dimension, metric, init_index=True, m: Optional[int] = 12, ef: Optional[int] = 64, ef_construction: Optional[int] = 64):
    namespace_table_name = QueryBuilder._quote_ident(f"{name}_namespaces")
    conn = global_pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute("CREATE TABLE IF NOT EXISTS {table_name} (id SERIAL PRIMARY KEY, name TEXT UNIQUE)".format(table_name=namespace_table_name))
            cur.execute("INSERT INTO {table_name} (name) VALUES ('')".format(table_name=namespace_table_name))
            query, params = translate_to_pyformat("INSERT INTO {table_name} (name, metric, dim, m, ef, ef_construction) VALUES ($1,$2,$3,$4,$5,$6)".format(table_name=indexes_table_name),(name, metric, dimension, m, ef, ef_construction))
            cur.execute(query, params)
        conn.commit()
    finally:
            global_pool.putconn(conn)
    index = Index(pool=global_pool, index_name=name)
    if init_index:
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
    

# Get all data from pynecone
def _get_ids_from_query(index, input_vector, namespace=""):
    results = index.query(vector=input_vector,
                          top_k=10000, include_values=False, namespace=namespace)
    ids = set()
    for result in results['matches']:
        ids.add(result['id'])
    return ids


def _get_all_ids_from_index(index, num_vectors, num_dimensions, namespace=""):
    import numpy as np
    all_ids = set()
    while len(all_ids) < num_vectors:
        input_vector = np.random.rand(num_dimensions).tolist()
        ids = _get_ids_from_query(index, input_vector, namespace)
        all_ids.update(ids)
    return all_ids

def _create_using_pinecone_index(lantern_index, pinecone_index, pinecone_index_info, pinecone_namespaces):
    for namespace in pinecone_namespaces:
        num_vectors = pinecone_namespaces[namespace]['vector_count']
        all_ids = _get_all_ids_from_index(pinecone_index, num_vectors=num_vectors, num_dimensions=int(pinecone_index_info.dimension), namespace=namespace)
        for chunk in tqdm(chunks(all_ids, 1000), write_bytes=False, bar_format="{percentage:3.0f}%"):
            data = pinecone_index.fetch(list(chunk), namespace)
            lantern_index.upsert(vectors=data.vectors.values(), copy=True, namespace=namespace)
        print(f"Namespace {namespace} copied")

def _create_using_pinecone_ids(lantern_index, pinecone_index, ids, namespace, pbar):
    for chunk in chunks(ids, 1000):
        data = pinecone_index.fetch(list(chunk), namespace)
        values = data.vectors.values()

        if len(values) == 0:
            continue
   
        lantern_index.upsert(vectors=values, copy=True, namespace=namespace)
        pbar.update(len(values))
        
def _create_using_pinecone_ids_parallel(lantern_index, pinecone_index, ids, num_vectors, namespace):
    threads = []
    cpu_count = os.cpu_count() or 1
    chunk_per_thread = math.ceil(len(ids) / cpu_count)
    thread_chunks = chunks(ids, chunk_per_thread)
    pbar = tqdm(total=min(num_vectors, len(ids)))

    for chunk in thread_chunks:
        thread = threading.Thread(target=_create_using_pinecone_ids, args=(lantern_index, pinecone_index, chunk, namespace, pbar))
        thread.start()
        threads.append(thread)

    for thread in threads:
        thread.join()

def create_from_pinecone(api_key: str, environment: str, index_name: str, namespace: Optional[str] = "", pinecone_ids: Optional[List[str]] =[], recreate=False, create_lantern_index: Optional[bool] = True, m: Optional[int] = 12, ef: Optional[int] = 64, ef_construction: Optional[int] = 64):
    pinecone.init(api_key=api_key, environment=environment)
    pinecone_index = pinecone.Index(index_name)

    if recreate:
        try:
            delete_index(index_name)
        except Exception as e:
            if "does not exist" in str(e):
                pass
            else:
                raise(e)
            

    index_stats_response = pinecone_index.describe_index_stats()
    index_info = pinecone.describe_index(index_name)

    supported_metrics = ["euclidean", "cosine", "hamming"]

    if index_info.metric not in supported_metrics:
        raise(Exception(f"Metric {index_info.metric} is not supported"))

    if not index_info.status or not index_info.status['ready']:
        raise(Exception(f"Index is not ready"))
        

    lantern_index = create_index(index_name, int(index_info.dimension), index_info.metric, init_index=False, m=m, ef=ef, ef_construction=ef_construction)
    lantern_index._init_index_tables()

    print("Copying data...")
    if not pinecone_ids or len(pinecone_ids) == 0:
        _create_using_pinecone_index(lantern_index, pinecone_index, index_info, index_stats_response.namespaces)
    else:
        _create_using_pinecone_ids_parallel(lantern_index, pinecone_index, pinecone_ids, index_stats_response.namespaces[namespace]['vector_count'], namespace)

    if create_lantern_index:
        print("Creating index...")
        lantern_index._init_index_indices()
    return lantern_index
    

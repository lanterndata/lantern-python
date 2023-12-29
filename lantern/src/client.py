import json
import numpy as np
import psycopg2.pool
from io import StringIO
from typing import (List, Optional, Union, Dict, Tuple, Any)
from psycopg2.extras import execute_values 
from contextlib import contextmanager
from .utils import get_vector_result, prepare_insert_data, default_max_db_connections, get_select_fields, translate_to_pyformat

class HNSWIndex():
    def __init__(self, dim: Optional[int] = None, m: Optional[int] = None, ef_construction: Optional[int] = None, ef_search: Optional[int] = None) -> None:
        self.m = m
        self.ef_construction = ef_construction
        self.ef_search = ef_search
        self.dim = dim

    def get_op_class(self, distance_type):
        if distance_type == 'euclidean':
            return 'dist_l2sq_ops'
        elif distance_type == 'cosine':
            return 'dist_cos_ops'
        elif distance_type == 'hamming':
            return 'dist_hamming_ops'

        raise(Exception(f"Invalid distance_type {distance_type}"))

    def create_index_query(self, table_name_quoted: str, column_name_quoted: str, index_name_quoted: str, distance_type: str) -> str:
        op_class = self.get_op_class(distance_type)

        with_clauses = []
        if self.m is not None:
            with_clauses.append(f"m = {self.m}")
        if self.ef_construction is not None:
            with_clauses.append(f"ef_construction = {self.ef_construction}")
        if self.ef_search is not None:
            with_clauses.append(f"ef = {self.ef_search}")
        if self.dim is not None:
            with_clauses.append(f"dim = {self.dim}")
        
        with_clause = ""
        if len(with_clauses) > 0:
            with_clause = "WITH (" + ", ".join(with_clauses) + ")"

        return "CREATE INDEX {index_name} ON {table_name} USING hnsw ({column_name} {op_class}) {with_clause};"\
            .format(index_name=index_name_quoted, table_name=table_name_quoted, column_name=column_name_quoted, op_class=op_class, with_clause=with_clause)



class QueryBuilder:
    def __init__(
            self,
            table_name: str,
            num_dimensions: int,
            id_type: str,
            distance_type: str,
            pgvectorcompat: bool
            ) -> None:
        self.table_name = table_name
        self.num_dimensions = num_dimensions
        self.pgvectorcompat = pgvectorcompat
        self.distance_type = self._parse_distance_type(distance_type)
        self.distance_operator = self._get_distance_operator()
        self.id_type = id_type.lower()

    def row_exists_query(self):
        return "SELECT 1 FROM {table_name} LIMIT 1".format(table_name=self._quote_ident(self.table_name))

    def _parse_distance_type(self, distance_type):
        if distance_type == 'euclidean' or distance_type == "l2sq":
            return 'euclidean'
        elif distance_type == 'cosine' or distance_type == "cos":
            return 'cosine'
        elif distance_type == 'hamming':
            return 'hamming'

        raise(Exception(f"Invalid distance type {distance_type}"))
 
    def _get_distance_operator(self):
        if not self.pgvectorcompat:
            return "<?>"
        
        if self.distance_type == 'euclidean':
            return "<->"
        elif self.distance_type == 'cosine':
            return "<=>"
        elif self.distance_type == 'hamming':
            return "<#>"

    def _get_distance_function(self, a, b):
        if self.distance_type == 'euclidean':
            return f'l2sq_dist({a}, {b})'
        elif self.distance_type == 'cosine':
            return f'cos_dist({a}, {b})'
        elif self.distance_type == 'hamming':
            return f'hamming_dist({a}, {b})'

    @staticmethod
    def _quote_ident(ident):
        return '"{}"'.format(ident.replace('"', '""'))

    def get_upsert_query(self):
        return "INSERT INTO {table_name} (id, embedding, metadata) VALUES %s ON CONFLICT DO NOTHING".format(table_name=self._quote_ident(self.table_name))

    def get_count_query(self):
        return "SELECT COUNT(*) as cnt FROM {table_name}".format(table_name=self._quote_ident(self.table_name))

    def get_create_query(self):
        return '''
                CREATE EXTENSION IF NOT EXISTS lantern;
                CREATE TABLE IF NOT EXISTS {table_name} (
                    id {id_type} PRIMARY KEY,
                    metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                    embedding REAL[{dimensions}] NOT NULL
                );
                
        '''.format(
            table_name=self._quote_ident(self.table_name), 
            id_type=self.id_type, 
            dimensions=self.num_dimensions,
        )

    def _get_embedding_index_name(self):
        return self._quote_ident(self.table_name+"_embedding_idx")

    def drop_embedding_index_query(self):
        return "DROP INDEX IF EXISTS {index_name};".format(index_name=self._get_embedding_index_name())

    def delete_all_query(self):
        return "TRUNCATE {table_name};".format(table_name=self._quote_ident(self.table_name))

    def delete_by_ids_query(self, ids: List[str]) -> Tuple[str, List]:
        query = "DELETE FROM {table_name} WHERE id = ANY($1::{id_type}[]);".format(
            table_name=self._quote_ident(self.table_name), id_type=self.id_type)
        return (query, [ids])
    
    def get_by_ids_query(self, select, ids) -> Tuple[str, List]:
        query = "SELECT {select_fields} FROM {table_name} WHERE id = ANY($1::{id_type}[])".format(
            table_name=self._quote_ident(self.table_name), select_fields=select, id_type=self.id_type)
        return (query, [ids])
    
    def get_by_id_query(self, select) -> str:
        query = "SELECT {select_fields} FROM {table_name} WHERE id = %s;".format(
            table_name=self._quote_ident(self.table_name), select_fields=select)
        return query

    def delete_by_metadata_query(self, filter: Dict[str, Union[str,Dict[str, str]]]) -> Tuple[str, List]:
        params: List[Any] = []
        (where, params) = self._where_clause_for_metadata(params, filter)
        query = "DELETE FROM {table_name} WHERE {where};".format(
            table_name=self._quote_ident(self.table_name), where=where)
        return (query, params)

    def drop_table_query(self):
        return "DROP TABLE IF EXISTS {table_name};".format(table_name=self._quote_ident(self.table_name))
    
    def create_embedding_index_query(self, index: HNSWIndex) -> str:
        column_name = "embedding"
        index_name = self._get_embedding_index_name()
        return index.create_index_query(self._quote_ident(self.table_name), self._quote_ident(column_name), index_name, self.distance_type)

    def create_metadata_index_query(self):
        return "CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} USING GIN(metadata jsonb_path_ops);".format(table_name=self._quote_ident(self.table_name), index_name=self._quote_ident(self.table_name + "_meta_idx"))


    def _where_clause_for_metadata(self, params: List, filter: Dict[str, Union[str,Dict[str, str]]]):
        has_predicate = False
        where_condition = []
        where_params = params
        predicates = {
            '$eq': '=',
            '$neq': '!=',
            '$lt': '<',
            '$lte': '<=',
            '$gt': '>',
            '$gte': '>=',
            '$in': 'IN',
            '$nin': 'NOT IN',
        }

        for key, val in filter.items():
            if type(val) is dict:
                has_predicate = True
                for pred_key, pred_val in val.items():
                    predicate = predicates.get(pred_key)
                    if not predicate:
                        raise Exception(f"Invalid predicate {pred_key}")
                    col_type = 'TEXT'

                    if type(pred_val) is int:
                        col_type = 'INT'
                    elif type(pred_val) is float:
                        col_type = 'FLOAT'

                    where_condition.append("(metadata->>'{key}')::{col_type} {predicate} (${idx})".format(key=key, col_type=col_type, predicate=predicate, idx=len(where_params) + 1))
                    where_params += [pred_val]
            else:
                where_condition.append("(metadata->>{key}) = (${idx})".format(key=key, idx=len(where_params) + 1))
                where_params += [val]

        if not has_predicate:
            where = "metadata @> ${index}".format(index=len(params)+1)
            json_object = json.dumps(filter)
            return [where], params + [json_object]
        else:
            return where_condition, where_params

    def get_update_by_id_query(self, embedding=None, metadata=None):
        query = "UPDATE {table_name} SET ".format(table_name=self._quote_ident(self.table_name))
        if embedding is not None and metadata is not None:
            query += "embedding=$2, metadata=$3 "
        elif metadata is not None:
            query += "metadata=$2 "
        elif embedding is not None:
            query += "embedding=$2 "

        query += "WHERE id=$1"

        return query
    

    def search_query(
            self, 
            query_embedding: Optional[Union[List[float], np.ndarray]], 
            limit: int = 10, 
            filter: Optional[Dict[str, Union[str,Dict[str, str]]]] = None,
            select: List[str] = [],
            ) -> Tuple[str, List]:

        select_fields = get_select_fields(select)
        params: List[Any] = []
        distance_query = ""
        if query_embedding is not None:
            distance = "embedding {op} ${index}".format(
                op=self.distance_operator, index=len(params)+1)
            distance_query = self._get_distance_function('embedding', f"${len(params)+1}")
            params = params + [query_embedding]
            order_by_clause = "ORDER BY {distance} ASC".format(
                distance=distance)
        else:
            distance = "-1.0"
            distance_query = distance
            order_by_clause = ""


        where_clauses = []
        if filter is not None:
            (where_filter, params) = self._where_clause_for_metadata(params, filter)
            where_clauses += where_filter

        if len(where_clauses) > 0:
            where = " AND ".join(where_clauses)
        else:
            where = "TRUE"

        query = '''
        SELECT
            {select_fields}, {distance_query} as distance
        FROM
           {table_name}
        WHERE 
           {where}
        {order_by_clause}
        LIMIT {limit}
        '''.format(select_fields=select_fields, distance=distance, order_by_clause=order_by_clause, where=where, table_name=self._quote_ident(self.table_name), limit=limit, distance_query=distance_query)
        return (query, params)

    def delete_table_query(self):
        return 'DROP TABLE IF EXISTS {table_name} CASCADE'.format(table_name=self._quote_ident(self.table_name))



        
class SyncClient:
    def __init__(
            self,
            table_name: str,
            dimensions: int,
            url: Optional[str] = None,
            pool: Optional[psycopg2.pool.SimpleConnectionPool] = None,
            distance_type: str = 'cosine',
            max_db_connections: Optional[int] = None,
            id_type: str = "TEXT",
            pgvectorcompat: bool = True,
            m: Optional[int] = 12,
            ef: Optional[int] = 64,
            ef_construction: Optional[int] = 64
            ) -> None:
        self.builder = QueryBuilder(
            table_name, dimensions, id_type, distance_type, pgvectorcompat)
        self.db_url = url
        self.pool = pool
        self.dimensions = dimensions
        self.table_name = table_name
        self.max_db_connections = max_db_connections
        self.pgvectorcompat = pgvectorcompat
        self.m = m
        self.ef = ef
        self.ef_construction = ef_construction


    @contextmanager
    def connect(self):
        if self.pool == None:
            if self.max_db_connections == None:
                self.max_db_connections = default_max_db_connections(self.db_url)

            self.pool = psycopg2.pool.SimpleConnectionPool(
                1, self.max_db_connections, dsn=self.db_url)

        connection = self.pool.getconn()
        try:
            yield connection
            connection.commit()
        finally:
            self.pool.putconn(connection)

    def exists(self):
        with self.connect() as conn:
            with conn.cursor() as cur:
                try:
                    cur.execute(self.builder.row_exists_query())
                    cur.fetchall()
                    return True
                except:
                    return False
    
    def close(self):
        if self.pool != None:
            self.pool.closeall()

    def create_table(self):
        query = self.builder.get_create_query()
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(query)

    def create_index(self):
        hnsw_index = HNSWIndex(dim=self.dimensions, m=self.m, ef_construction=self.ef_construction, ef_search=self.ef)
        hnsw_query = self.builder.create_embedding_index_query(hnsw_index)
        meta_query = self.builder.create_metadata_index_query()
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(hnsw_query)
                cur.execute(meta_query)

    def upsert(self, data):
        if data is None or len(data) == 0:
            raise(Exception("Data can not be empty"))

        query = self.builder.get_upsert_query()
        
        values = prepare_insert_data(data)

        with self.connect() as conn:
            with conn.cursor() as cur:
                return execute_values(cur, query, (values,))
    
    def upsert_many(self, data):
        if data is None or len(data) == 0:
            raise(Exception("Data can not be empty"))

        query = self.builder.get_upsert_query()
        
        values = list(map(prepare_insert_data, data))

        with self.connect() as conn:
            with conn.cursor() as cur:
                return execute_values(cur, query, values)

    def bulk_insert(self, rows):
        f = StringIO("")
        rows_len = len(rows)
        for i in range(len(rows)):
            data = prepare_insert_data(rows[i])

            id = data[0]
            embedding = data[1]
            metadata = data[2]

            metadata = metadata.replace('\\', '\\\\').replace('"', '\\"')
            f.write(f"{id}\t{metadata}\t{{{str(embedding)[1:-1]}}}")
            if i != rows_len - 1:
                f.write('\n')
        f.seek(0)
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.copy_expert('COPY {table_name} (id, metadata, embedding) FROM STDIN'.format(table_name=QueryBuilder._quote_ident(self.table_name)), f)

                
    def update_by_id(self, id, embedding=None, metadata=None):
        query = self.builder.get_update_by_id_query(embedding, metadata)
        with self.connect() as conn:
            with conn.cursor() as cur:
                if metadata is not None:
                    metadata = json.dumps(metadata)

                params = tuple(filter(lambda x: x is not None, [id, embedding, metadata]))
                query, params = translate_to_pyformat(query, params)
                cur.execute(query, params)
                
    def delete_by_ids(self, ids):
        query, params = self.builder.delete_by_ids_query(ids)
        query, params = translate_to_pyformat(query, params)
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)

                
    def drop(self):
        query = self.builder.delete_table_query()
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(query)

    def get_by_id(self, id, select_fields=[]):
        query = self.builder.get_by_id_query(get_select_fields(select_fields))
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(query, id)
                return get_vector_result(cur.fetchall(), select_fields, True)
    
    def get_by_ids(self, ids=[], select_fields=[]):
        query, params = self.builder.get_by_ids_query(get_select_fields(select_fields), ids)
        query, params = translate_to_pyformat(query, params)
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                return get_vector_result(cur.fetchall(), select_fields)
    
    def count(self):
        query = self.builder.get_count_query()
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                return cur.fetchall()[0][0]

    def search(self, query_id: Optional[str] = None, query_embedding: Optional[List[float|int]] = None, limit: Optional[int] = 10, filter: Optional[dict] = None, select_fields: Optional[List[str]] = []):
        if not query_id and not query_embedding:
            raise(Exception("Please provide 'query_id' or 'query_embedding' argument for search"))
        if query_id:
            row = self.get_by_id([query_id], ['embedding'])
            if row is None:
                return []
            else:
                query_embedding = row.embedding
  
        query, params = self.builder.search_query(query_embedding, limit=limit, filter=filter, select=select_fields)
        query, params = translate_to_pyformat(query, params)
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(f"SET hnsw.init_k={limit}")
                cur.execute("SET enable_seqscan=OFF")
                if not self.pgvectorcompat:
                  cur.execute(f"SET lantern.pgvectorcompat=OFF")
                cur.execute(query, params)
                return get_vector_result(cur.fetchall(), select_fields)


import os
import sys
sys.path.append('../src')
from lantern import SyncClient

DB_URL = os.environ.get("DB_URL")

if DB_URL is None:
    raise(Exception("Please provide 'DB_URL' env variable"))

def test_client():
    client = SyncClient(url=DB_URL, table_name="small_world", dimensions=3, distance_type="l2sq", m=12, ef=64, ef_construction=64)
    try:
      client.drop()
    except:
     pass
    client.create_table()
    client.bulk_insert([
      ("1", [0,0,0], { "name": "a" }),
      ("2", [0,1,0], { "name": "b" }),
      ("3", [0,0,1], { "name": "c" })
    ])
    client.create_index()

# Select specific fields
    vec_by_id = client.get_by_id(id="1", select_fields=["id", "metadata"])
    assert(vec_by_id.embedding == None)
# Get by id
    vec_by_id = client.get_by_id("1")
    assert(vec_by_id.id == "1")

# Get by ids
    vectors_by_ids = client.get_by_ids(["1", "3"])
    assert(len(vectors_by_ids) == 2)
    assert(vectors_by_ids[0].id == "1")
    assert(vectors_by_ids[1].id == "3")

# Insert one
    client.upsert(("4", [1,0,0], { "name": "d" }))

# Update
    client.update_by_id(id="4", metadata={ "name": "4" })

# Get row count
    row_count = client.count()
    assert(row_count == 4)
    
    vec_by_id = client.get_by_id(id="4", select_fields=["id", "embedding", "metadata"])
    assert(vec_by_id.metadata.name == "4")

    vectors = client.search(query_id="4")
    assert(len(vectors) == row_count)
    assert(vectors[0].id == "4")
    assert(vectors[0].distance == 0)
    vectors = client.search(query_embedding=vec_by_id.embedding, limit=2, filter={"name": "a"}, select_fields=["id"])
    assert(len(vectors) == 1)
    assert(vectors[0].id == "1")
    assert(vectors[0].metadata == None)
    assert(vectors[0].embedding == None)


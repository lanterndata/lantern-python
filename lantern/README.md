# Python Client for Lantern

## Install

```sh
pip install lantern-client
```

## Basic usage

```python
from lantern_client import SyncClient

DB_URL="postgresql://postgres@localhost:5432/lantern"
client = SyncClient(url=DB_URL, table_name="small_world", dimensions=3, distance_type="l2sq", m=12, ef=64, ef_construction=64)
client.bulk_insert([
  ("1", [0,0,0], { "name": "a" }),
  ("2", [0,1,0], { "name": "b" }),
  ("3", [0,0,1], { "name": "c" })
])
client.create_index()

# Get by id
vec_by_id = client.get_by_id("1")
# Select specific fields
vec_by_id = client.get_by_id(id="1", select_fields=["id", "metadata"])

# Get by ids
vectors_by_ids = client.get_by_ids(["1", "3"])

# Insert one
client.upsert(("4", [1,0,0], { "name": "d" }))

# Update
client.update_by_id(id="4", metadata={ "name": "d" }))

# Get row count
row_count = client.count()

vectors = client.search(query_id="1")
vectors = client.search(query_embedding=vec_by_id.embedding, limit=2, filter={"name": "a"}, select_fields=["id"])
```

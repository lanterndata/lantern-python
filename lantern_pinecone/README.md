# Lantern client compatible with Pinecone API

## Install

```sh
pip install lantern-pinecone
```

## Sync from Pinecone to Lantern

```python
import lantern_pinecone
from getpass import getpass

lantern_pinecone.init('postgres://postgres@localhost:5432')

pinecone_ids = list(map(lambda x: str(x), range(100000)))

index = lantern_pinecone.create_from_pinecone(
        api_key=getpass("Pinecone API Key"),
        environment="us-east-1-aws",
        index_name="sift100k",
        namespace="",
        pinecone_ids=pinecone_ids,
        recreate=True,
        create_lantern_index=True)

index.describe_index_stats()

index.query(top_k=10, id='45500', namespace="")
```

> **_NOTE:_** If you pass `create_lantern_index=False` only data will be copied under the table of your index name (in this example `sift100k`) and you can create an index later externally. Without the index most of the index operations will not be accessible via this client.

## Extract Metadata Fields

When copying from Pinecone we create a table in this structure: `sql (id TEXT, embedding REAL[], metadata jsonb)`
If you are planning to use the index with raw sql clients, you may want to extract metadata into separate columns, so you could have more complex/nice looking queries over your metadata fields.
So if our metadata has this shape `{ "title": string, "description": string }`, we can extract it using this query:

```sql
BEGIN;
ALTER TABLE sift100k
ADD COLUMN title TEXT,
ADD COLUMN description TEXT;

-- Update the new columns with data extracted from the JSONB column
UPDATE sift100k
SET
  title = metadata->>'title',
  description = metadata->>'description';


-- Optionally drop the metadata column
ALTER TABLE sift100k DROP COLUMN metadata;

COMMIT;
```

After doing this your index will most likely be uncomaptible with this python client, and you should use it via raw sql client like `psycopg2`

## Index operations

```python
import os
import lantern_pinecone
import pandas as pd

LANTERN_DB_URL = os.environ.get('LANTERN_DB_URL') or 'postgres://postgres@localhost:5432'
lantern_pinecone.init(LANTERN_DB_URL)

# Giving our index a name
index_name = "hello-lantern"

# Delete the index, if an index of the same name already exists
if index_name in lantern_pinecone.list_indexes():
    lantern_pinecone.delete_index(index_name)


import time

dimensions = 3
lantern_pinecone.create_index(name=index_name, dimension=dimensions, metric="cosine")
index = lantern_pinecone.Index(index_name=index_name)


df = pd.DataFrame(
    data={
        "id": ["A", "B"],
        "vector": [[1., 1., 1.], [1., 2., 3.]]
    })

# Insert vectors
index.upsert(vectors=zip(df.id, df.vector))

index.describe_index_stats()

index.query(
    vector=[2., 2., 2.],
    top_k=5,
    include_values=True) # returns top_k matches


lantern_pinecone.delete_index(index_name)
```

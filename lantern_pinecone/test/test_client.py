import os
import sys
import lantern_pinecone

sys.path.append('../src')

DB_URL = os.environ.get("DB_URL")

if DB_URL is None:
    raise (Exception("Please provide 'LANTERN_DB_URL' env variable"))

lantern_pinecone.init(DB_URL)


def test_client():
    # Initialize the index
    index_name = "test_index"
    if index_name in lantern_pinecone.list_indexes():
        lantern_pinecone.delete_index(index_name)

    dimensions = 3
    lantern_pinecone.create_index(
        name=index_name, dimension=dimensions, metric="cosine")
    index = lantern_pinecone.Index(index_name=index_name)

    # Insert data into the index
    data = [
        ("1", [0, 0, 0]),
        ("2", [0, 1, 0]),
        ("3", [0, 0, 1])
    ]
    index.upsert(vectors=data)

    # Check index stats
    stats = index.describe_index_stats()
    assert (stats['total_count'] == 3)

    # Query the index
    results = index.query(vector=[0, 0, 0], top_k=2, include_values=True)
    assert (len(results) == 2)
    assert (results[0]['id'] == "1")

    # Delete the index
    lantern_pinecone.delete_index(index_name)
    assert (index_name not in lantern_pinecone.list_indexes())

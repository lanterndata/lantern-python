from lantern import SyncClient
import os

DB_URL = os.environ.get("DB_URL")

if DB_URL is None:
    raise (Exception("Please provide 'DB_URL' env variable"))


def test_client():
    # Initialize the SyncClient with the database URL and table configuration
    client = SyncClient(
        url=DB_URL,
        table_name="small_world",
        dimensions=3,
        distance_type="l2sq",
        m=12,
        ef=64,
        ef_construction=64,
    )

    # Attempt to drop the existing table if it exists
    try:
        client.drop()
    except:
        pass

    # Create a new table
    client.create_table()

    # Bulk insert data into the table
    client.bulk_insert(
        [
            ("1", [0, 0, 0], {"name": "a"}),
            ("2", [0, 1, 0], {"name": "b"}),
            ("3", [0, 0, 1], {"name": "c"}),
        ]
    )

    # Create an index to optimize search queries
    client.create_index()

    # Retrieve a specific record by ID, selecting only certain fields
    vec_by_id = client.get_by_id(id="1", select_fields=["id", "metadata"])
    assert vec_by_id.embedding is None

    # Retrieve a record by ID without field restrictions
    vec_by_id = client.get_by_id("1")
    assert vec_by_id.id == "1"

    # Retrieve multiple records by their IDs
    vectors_by_ids = client.get_by_ids(["1", "3"])
    assert len(vectors_by_ids) == 2
    assert vectors_by_ids[0].id == "1"
    assert vectors_by_ids[1].id == "3"

    # Insert or update a single record
    client.upsert(("4", [1, 0, 0], {"name": "d"}))

    # Update the metadata of a record by its ID
    client.update_by_id(id="4", metadata={"name": "4"})

    # Get the total number of records in the table
    row_count = client.count()
    assert row_count == 4

    # Retrieve a record by ID, selecting specific fields
    vec_by_id = client.get_by_id(id="4", select_fields=[
                                 "id", "embedding", "metadata"])
    assert vec_by_id.metadata["name"] == "4"

    # Search for vectors similar to the one with ID "4"
    vectors = client.search(query_id="4")
    assert len(vectors) == row_count
    assert vectors[0].id == "4"
    assert vectors[0].distance == 0

    # Search for vectors using the embedding of the vector with ID "4"
    # Limit the results to 2 and apply a filter on the metadata
    vectors = client.search(
        query_embedding=vec_by_id.embedding,
        limit=2,
        filter={"name": "a"},
        select_fields=["id"],
    )
    assert len(vectors) == 1
    assert vectors[0].id == "1"
    assert vectors[0].metadata is None
    assert vectors[0].embedding is None

    # Search for vectors using the embedding of the vector with ID "4"
    # Limit the results to 2 and apply an $in filter on the metadata
    vectors = client.search(
        query_embedding=vec_by_id.embedding,
        limit=2,
        filter={"name": {"$in": "a"}},
        select_fields=["id"],
    )
    assert len(vectors) == 1
    assert vectors[0].id == "1"
    assert vectors[0].metadata is None
    assert vectors[0].embedding is None

# Contributing to lantern-python

## Prerequisites

* Python 3.8 or higher
* Postgres database with Lantern extensions installed

## Installation

1. Fork this repository to your own GitHub account and then clone it to your local device.

    ```bash
    git clone https://github.com/your-username/lantern-python.git
    ```

2. Navigate to the cloned project directory and set up the development environment

    ```bash
    cd lantern-python
    python3 -m venv .venv
    source .venv/bin/activate # On windows use .venv\Scripts\activate
    ```

3. Install the required dependencies

    ```bash
    pip install -r requirements.txt

    pip install -r lantern/requirements.txt
    pip install -e lantern

    pip install -r lantern_pinecone/requirements.txt
    pip install -e lantern_pinecone

    pip install -r lantern_django/requirements.txt
    pip install -e lantern_django

    pre-commit install
    ```

4. Set DB_URL in environment

    ```bash
    export DB_URL=postgresql://user:password@localhost:5432/lantern
    ```

## Style guide

We use Black for code formatting.

```bash
black .
```

## Running tests

Run tests using pytest:

```bash
# To run all tests
pytest

# To run specific tests
pytest test/test_lantern.py
pytest test/test_pinecone.py
pytest test/test_django.py
```

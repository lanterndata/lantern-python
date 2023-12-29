.PHONY: test

prepare-test:
	python3 -m venv .venv && source .venv/bin/activate && python3 -m pip install -e . && python3 -m pip install -r requirements.txt

test:
	.venv/bin/pytest 

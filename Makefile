PY = .venv/bin/python

setup:
	python3.11 -m venv .venv
	$(PY) -m pip install -r requirements.txt

sql:
	$(PY) -m src.run_sql

test:
	$(PY) -m pytest -q

.PHONY: setup sql test

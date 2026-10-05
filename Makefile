PY = .venv/bin/python

all: sql ab charts notebook

setup:
	python3.11 -m venv .venv
	$(PY) -m pip install -r requirements.txt

sql:
	$(PY) -m src.run_sql

ab:
	$(PY) -m src.ab_test

charts:
	$(PY) -m src.make_charts

notebook:
	$(PY) -m jupyter nbconvert --to notebook --execute --inplace notebooks/analysis.ipynb

test:
	$(PY) -m pytest -q

.PHONY: all setup sql ab charts notebook test

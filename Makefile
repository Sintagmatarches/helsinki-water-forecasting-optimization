.PHONY: data experiment report test lint typecheck all

data:
	python -m helsinki_water.cli acquire

experiment:
	python -m helsinki_water.cli run

report:
	python -m helsinki_water.cli report

test:
	pytest

lint:
	ruff check .

typecheck:
	mypy src

all: data experiment report test lint typecheck

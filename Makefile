UV ?= uv
PYTHONPATH := src

.PHONY: setup lock test lint check run generate-data validate-data ingest-excel ingest-delimited ingest-json check-ocr-runtime extract-pdf extract-image demo clean

setup:
	$(UV) sync --locked

lock:
	$(UV) lock

test:
	PYTHONPATH=$(PYTHONPATH) $(UV) run python -m unittest discover -s tests -p 'test_*.py' -v

lint:
	$(UV) run python -m compileall -q src tests scripts

check: lint test

run:
	PYTHONPATH=$(PYTHONPATH) $(UV) run python -m faro.main

generate-data:
	PYTHONPATH=$(PYTHONPATH) $(UV) run python scripts/generate_synthetic_data.py

validate-data:
	PYTHONPATH=$(PYTHONPATH) $(UV) run python scripts/validate_dataset.py

ingest-excel:
	PYTHONPATH=$(PYTHONPATH) $(UV) run python scripts/ingest_excel.py

ingest-delimited:
	@test -n "$(SOURCES)" || (echo "Usage: make ingest-delimited SOURCES='--source products=products.csv --source sales=sales.tsv'" && exit 2)
	PYTHONPATH=$(PYTHONPATH) $(UV) run python scripts/ingest_delimited.py $(SOURCES)

ingest-json:
	@test -n "$(SOURCES)" || (echo "Usage: make ingest-json SOURCES='--source products=products.json --source sales=sales.ndjson'" && exit 2)
	PYTHONPATH=$(PYTHONPATH) $(UV) run python scripts/ingest_json_records.py $(SOURCES)

check-ocr-runtime:
	PYTHONPATH=$(PYTHONPATH) $(UV) run python scripts/check_ocr_runtime.py

extract-pdf:
	@test -n "$(PDF)" || (echo "Usage: make extract-pdf PDF=path/to/document.pdf" && exit 2)
	PYTHONPATH=$(PYTHONPATH) $(UV) run python scripts/extract_pdf.py "$(PDF)"

extract-image:
	@test -n "$(IMAGE)" || (echo "Usage: make extract-image IMAGE=path/to/document.png" && exit 2)
	PYTHONPATH=$(PYTHONPATH) $(UV) run python scripts/extract_image.py "$(IMAGE)"

demo:
	PYTHONPATH=$(PYTHONPATH) $(UV) run python scripts/run_demo.py

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage build dist
	find . -type d -name __pycache__ -prune -exec rm -rf {} +

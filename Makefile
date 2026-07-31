UV ?= uv
PYTHONPATH := src

.PHONY: setup lock test lint check run generate-data validate-data demo clean

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

demo:
	PYTHONPATH=$(PYTHONPATH) $(UV) run python scripts/run_demo.py

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage build dist
	find . -type d -name __pycache__ -prune -exec rm -rf {} +

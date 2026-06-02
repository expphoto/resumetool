.PHONY: venv install install-min wizard run serve test lint seed seed-reset help

help:
	@echo "Targets:"
	@echo "  venv           Create a fresh .venv"
	@echo "  install        Install the project (editable, with dev extras)"
	@echo "  install-min    Install just the minimum runtime deps"
	@echo "  wizard         Run the resume tailoring CLI wizard"
	@echo "  run            Show CLI help"
	@echo "  serve          Run the HR portal (FastAPI + uvicorn)"
	@echo "  seed           Seed the demo DB with synthetic candidates (50 by default)"
	@echo "  seed-reset     Wipe and reseed the demo DB"
	@echo "  test           Run the full test suite"
	@echo "  lint           Run ruff over src/, scripts/, and tests/"

venv:
	python3 -m venv .venv --upgrade-deps
	. .venv/bin/activate; python -m pip install -U pip setuptools wheel

install: venv
	.venv/bin/python -m pip install -e '.[dev]'

install-min: venv
	.venv/bin/python -m pip install 'typer[all]' rich'

wizard:
	PYTHONPATH=src .venv/bin/python -m resumetool.cli wizard

run:
	PYTHONPATH=src .venv/bin/python -m resumetool.cli --help

serve:
	PYTHONPATH=src .venv/bin/python -m uvicorn resumetool.server.app:app --reload --host 0.0.0.0 --port 8000

seed:
	PYTHONPATH=src .venv/bin/python -m scripts.seed_demo --count 50

seed-reset:
	PYTHONPATH=src .venv/bin/python -m scripts.seed_demo --count 50 --reset

test:
	PYTHONPATH=src .venv/bin/python -m pytest tests/ -q

lint:
	.venv/bin/ruff check src/ scripts/ tests/

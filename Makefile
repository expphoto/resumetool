.PHONY: venv install install-min wizard run help

help:
	@echo "Targets: venv, install, install-min, wizard, run"

venv:
	python3 -m venv .venv --upgrade-deps
	. .venv/bin/activate; python -m pip install -U pip setuptools wheel

install: venv
	.venv/bin/python -m pip install -e '.[dev]'

install-min: venv
	.venv/bin/python -m pip install 'typer[all]' rich

wizard:
	PYTHONPATH=src .venv/bin/python -m resumetool.cli wizard

run:
	PYTHONPATH=src .venv/bin/python -m resumetool.cli --help

PY ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)

.PHONY: test demo demo-voice

test:
	$(PY) -m pytest -q

demo:
	PYTHONPATH=src $(PY) -m fleek_market.cli

demo-voice:
	PYTHONPATH=src $(PY) -m fleek_market.cli --voice

PY ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
SEED ?=
RUN = PYTHONPATH=src $(PY) -m fleek_market.cli $(if $(SEED),--seed $(SEED))

.PHONY: test demo demo-voice

test:
	$(PY) -m pytest -q

demo:
	$(RUN)

demo-voice:
	$(RUN) --voice

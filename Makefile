# Convenience targets (Linux/macOS/Git Bash). Windows users: use setup.ps1 / demo.ps1.

PY ?= python
IMAGE ?= samples/me.jpg
CHAIN ?= local

.PHONY: install models test contract-test chain deploy run clean

install:
	$(PY) -m pip install -r requirements.txt

models:
	$(PY) scripts/fetch_models.py

test:
	$(PY) -m pytest

contract-test:
	npx hardhat test

chain:
	npx hardhat node

deploy:
	$(PY) scripts/deploy.py --chain $(CHAIN)

run:
	$(PY) -m faceproof run --image $(IMAGE) --chain $(CHAIN) --i-have-consent --html

clean:
	rm -rf out/scan_* out/ev_*.json out/case_*.html .pytest_cache __pycache__

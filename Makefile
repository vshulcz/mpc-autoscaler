SHELL := /bin/bash

TOY_LOAD_DIR ?= toy-load

.PHONY: help fmt fmt-check vet test helm-lint helm-template check coverage toy-load-run toy-load-check toy-load-race toy-load-build toy-load-docker-build toy-load-coverage analysis-check analysis-coverage shell-check json-check

help:
	@printf "%-22s %s\n" "check" "Run default repository checks"
	@printf "%-22s %s\n" "fmt" "Format toy-load Go sources"
	@printf "%-22s %s\n" "fmt-check" "Fail if Go sources need formatting"
	@printf "%-22s %s\n" "vet" "Run Go vet for toy-load"
	@printf "%-22s %s\n" "test" "Run Go tests for toy-load"
	@printf "%-22s %s\n" "helm-lint" "Lint toy-load Helm chart"
	@printf "%-22s %s\n" "helm-template" "Render toy-load Helm chart"
	@printf "%-22s %s\n" "coverage" "Generate Go and Python coverage reports"
	@printf "%-22s %s\n" "toy-load-run" "Run toy-load locally"
	@printf "%-22s %s\n" "toy-load-check" "Run toy-load checks"
	@printf "%-22s %s\n" "toy-load-race" "Run toy-load race tests"
	@printf "%-22s %s\n" "toy-load-build" "Build toy-load binary"
	@printf "%-22s %s\n" "toy-load-docker-build" "Build toy-load container image"
	@printf "%-22s %s\n" "toy-load-coverage" "Generate toy-load Go coverage report"
	@printf "%-22s %s\n" "analysis-check" "Run dependency-light analysis checks"
	@printf "%-22s %s\n" "analysis-coverage" "Generate analysis Python coverage report"
	@printf "%-22s %s\n" "shell-check" "Check shell script syntax"
	@printf "%-22s %s\n" "json-check" "Validate dashboard JSON files"

check: toy-load-check analysis-check shell-check json-check

fmt:
	$(MAKE) -C $(TOY_LOAD_DIR) fmt

fmt-check:
	$(MAKE) -C $(TOY_LOAD_DIR) fmt-check

vet:
	$(MAKE) -C $(TOY_LOAD_DIR) vet

test:
	$(MAKE) -C $(TOY_LOAD_DIR) test

helm-lint:
	$(MAKE) -C $(TOY_LOAD_DIR) helm-lint

helm-template:
	$(MAKE) -C $(TOY_LOAD_DIR) helm-template

coverage: toy-load-coverage analysis-coverage

toy-load-run:
	$(MAKE) -C $(TOY_LOAD_DIR) run

toy-load-check:
	$(MAKE) -C $(TOY_LOAD_DIR) check

toy-load-race:
	$(MAKE) -C $(TOY_LOAD_DIR) test-race

toy-load-build:
	$(MAKE) -C $(TOY_LOAD_DIR) build

toy-load-docker-build:
	$(MAKE) -C $(TOY_LOAD_DIR) docker-build

toy-load-coverage:
	$(MAKE) -C $(TOY_LOAD_DIR) coverage

analysis-check:
	PYTHONPATH=analysis python3 -m unittest discover -s analysis/tests
	python3 -m compileall -q analysis

analysis-coverage:
	mkdir -p coverage
	@python3 -c 'import coverage, sys; sys.exit(0 if getattr(coverage, "__version__", None) else 1)' >/dev/null 2>&1 || { printf 'Install coverage.py first: python3 -m pip install coverage\n'; exit 1; }
	PYTHONPATH=analysis python3 -m coverage run --source=analysis/mpc_autoscaler_analysis -m unittest discover -s analysis/tests
	python3 -m coverage xml -o coverage/analysis.xml
	python3 -m coverage report

shell-check:
	bash -n experiments/package-thesis-evidence.sh
	bash -n loadgen/scripts/*.sh

json-check:
	python3 -m json.tool dashboards/toy-load-dashboard.json >/dev/null
	python3 -m json.tool deploy/monitoring/dashboards/toy-load-dashboard.json >/dev/null
	python3 -m json.tool toy-load/deploy/helm/toy-load/files/toy-load-dashboard.json >/dev/null
	python3 -m json.tool toy-load/deploy/helm/toy-load/values.schema.json >/dev/null

SHELL=/bin/bash

.PHONY: help
help:
	@awk -F':.*##' '/^[-_a-zA-Z0-9]+:.*##/{printf"%-12s\t%s\n",$$1,$$2}' $(MAKEFILE_LIST) | sort

format: ## Format
	pinact run
	npx prettier -w .
	black .

lint: lint-gha lint-renovate ## Lint
	npx prettier -c .
	yamllint .
	shellcheck scripts/*.sh
	flake8

lint-gha:
	npx prettier -c .github/workflows
	yamllint .github/workflows
	actionlint
	zizmor .
	ghalint run

lint-renovate:
	npx --package renovate@latest -- renovate-config-validator --strict

test: ## Test
	python3 -m unittest tests/*.py

SHELL=/bin/bash

.PHONY: help
help:
	@awk -F':.*##' '/^[-_a-zA-Z0-9]+:.*##/{printf"%-12s\t%s\n",$$1,$$2}' $(MAKEFILE_LIST) | sort

format: ## Format
	pinact run
	npx prettier -w .

lint: lint-gha lint-renovate ## Lint
	npx prettier -c .
	yamllint .

lint-gha:
	npx prettier -c .github/
	yamllint .github/
	actionlint
	zizmor .
	ghalint run
	shellcheck scripts/*.sh

lint-renovate:
	npx --package renovate@latest -- renovate-config-validator --strict

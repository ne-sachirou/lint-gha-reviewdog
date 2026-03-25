SHELL=/bin/bash

.PHONY: help
help:
	@awk -F':.*##' '/^[-_a-zA-Z0-9]+:.*##/{printf"%-12s\t%s\n",$$1,$$2}' $(MAKEFILE_LIST) | sort

format: ## Format
	pinact run
	npx prettier -w *.md
	npx prettier -w .github/
	npx prettier -w .yamllint.yaml

lint: lint-gha lint-renovate ## Lint
	yamllint .

lint-gha:
	npx prettier -c .github/
	yamllint .github/
	shellcheck .github/actions/*/scripts/*.sh
	actionlint
	zizmor .
	ghalint run

lint-renovate:
	npx --package renovate@latest -- renovate-config-validator --strict

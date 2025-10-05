# ------------------------------------------------------
# HELP
# ------------------------------------------------------
.PHONY: help
help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

# ------------------------------------------------------
# LOCAL COMMANDS
# ------------------------------------------------------
.PHONY: test_unit
test: ## Run unit tests
	@poetry run pytest ./tests


# this linter just lints src/services/notification/ and tests folders.
# it should gradually covers all other parts of the code as soon all errors have been fixed
.PHONY: lint
lint: ## Run linters with auto-fix.
	@poetry run pre-commit run --all-files

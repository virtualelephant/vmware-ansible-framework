# Makefile — repo-wide task runner + packaging/release
# Usage examples:
#   make                          # show help
#   make package                  # create artifacts/<repo>-<version>.tar.gz
#   make release VERSION=1.0.0    # tag v1.0.0, package, and (in CI) publish Release + asset
#   make clean                    # prune artifacts/ to keep 5 newest tarballs
#   make clean-all                # remove artifacts/ entirely

SHELL := /bin/bash
.DEFAULT_GOAL := help

# ----------------------------
# Version resolution precedence
# ----------------------------
# 1) Explicit VERSION=… from user or CI variable
# 2) Tag pipeline (CI_COMMIT_TAG), with leading "v" stripped
# 3) Fallback to short SHA (CI_COMMIT_SHA or local HEAD)
VERSION_FROM_TAG := $(shell bash -c '[[ -n "$${CI_COMMIT_TAG:-}" ]] && echo "$$CI_COMMIT_TAG" | sed -E "s/^v//" || true')
VERSION_SHORT := $(shell bash -c 'set -euo pipefail; \
  if [[ -n "$${CI_COMMIT_SHA:-}" ]]; then echo "$$CI_COMMIT_SHA" | cut -c1-8; \
  else git rev-parse --short=8 HEAD; fi')

ifeq ($(strip $(VERSION)),)
  ifneq ($(strip $(VERSION_FROM_TAG)),)
    VERSION := $(VERSION_FROM_TAG)
  else
    VERSION := $(VERSION_SHORT)
  endif
endif

# ----------------------------
# Names / paths
# ----------------------------
REPO_NAME := $(shell basename "$$(git rev-parse --show-toplevel)")
ARTIFACTS_DIR := artifacts
TARBALL := $(ARTIFACTS_DIR)/$(REPO_NAME)-$(VERSION).tar.gz

# Include everything except .git and artifacts/ itself
TAR_INCLUDE := .
TAR_EXCLUDES := --exclude .git --exclude $(ARTIFACTS_DIR)

# Tag/release metadata
TAG_PREFIX ?= v
TAG := $(TAG_PREFIX)$(VERSION)
GIT_REMOTE ?= origin
RELEASE_NAME := $(REPO_NAME) $(TAG)

# ----------------------------
# Phony targets
# ----------------------------
.PHONY: help bootstrap lint test build run \
        version validate-version package \
        clean clean-all release

help: ## Show this help
	@grep -E '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) \
	 | sed -E 's/:.*?## /:\t/' \
	 | sort

bootstrap: ## Install local dev deps (placeholder)
	@echo "No bootstrap steps defined yet."

lint: ## Run linters (placeholder)
	@echo "Running linters…"
	@# e.g. ruff check . && yamllint .

test: ## Run tests (placeholder)
	@echo "Running tests…"
	@# e.g. pytest -q

build: lint test ## Build the project (placeholder)
	@echo "Building…"
	@# e.g. python -m build

run: build ## Run the app locally (placeholder)
	@echo "Running app…"
	@# e.g. ./bin/run.sh

version: ## Print the computed VERSION
	@echo $(VERSION)

validate-version: ## Fail if VERSION contains characters that would break tags/files
	@bash -c 'set -euo pipefail; \
	  v="$(VERSION)"; \
	  if [[ -z "$$v" ]]; then echo "VERSION is empty"; exit 1; fi; \
	  if [[ "$$v" =~ [[:space:]/] ]]; then \
	    echo "Invalid VERSION (contains space or /): $$v"; exit 1; fi'

package: validate-version ## Create versioned tarball in artifacts/
	@mkdir -p $(ARTIFACTS_DIR)
	@echo "Packaging $(REPO_NAME) -> $(TARBALL)"
	@tar -czf $(TARBALL) $(TAR_EXCLUDES) $(TAR_INCLUDE)
	@echo "Created $(TARBALL)"

# Keep only the 5 most recent tarballs; delete the rest (safe if <5 exist)
clean: ## Prune old tarballs in artifacts/ keeping the 5 newest
	@echo "Pruning old tarballs in $(ARTIFACTS_DIR)/ (keep latest 5)…"
	@bash -c 'set -euo pipefail; \
	  shopt -s nullglob; \
	  files=($(ARTIFACTS_DIR)/*.tar.gz); \
	  if (( $${#files[@]} > 5 )); then \
	    to_delete=$$(ls -1t $(ARTIFACTS_DIR)/*.tar.gz | tail -n +6); \
	    echo "$$to_delete" | xargs -r rm -f; \
	    echo "Deleted:"; echo "$$to_delete"; \
	  else \
	    echo "Nothing to prune."; \
	  fi'

clean-all: ## Remove the entire artifacts directory
	@echo "Removing $(ARTIFACTS_DIR)/"
	@rm -rf $(ARTIFACTS_DIR)

# Tag repo, package, and (in GitLab CI) create/update Release + attach tarball
release: validate-version package ## Tag and publish GitLab Release (in CI)
	@echo "Tagging repository with $(TAG)…"
	@bash -c 'set -euo pipefail; \
	  if ! git rev-parse "$(TAG)" >/dev/null 2>&1; then \
	    git tag -a "$(TAG)" -m "Release $(TAG)"; \
	    git push $(GIT_REMOTE) "$(TAG)"; \
	  else \
	    echo "Tag $(TAG) already exists."; \
	  fi'

# Only attempt the GitLab Release upload when CI env vars are present.
# This avoids macOS/local quoting issues entirely.
ifeq ($(strip $(CI_JOB_TOKEN)$(CI_API_V4_URL)$(CI_PROJECT_ID)),)
release:
	@echo "Not in GitLab CI with API env; release asset upload skipped."
else
release:
	@bash -c 'set -euo pipefail; \
	  echo "Creating/updating GitLab Release $(TAG) and uploading asset…"; \
	  # Create or update Release
	  curl -sfS --header "JOB-TOKEN: $$CI_JOB_TOKEN" \
	    --data-urlencode "name=$(RELEASE_NAME)" \
	    --data-urlencode "tag_name=$(TAG)" \
	    --data-urlencode "description=Automated release for $${CI_COMMIT_SHA:-local}" \
	    --request POST "$$CI_API_V4_URL/projects/$$CI_PROJECT_ID/releases" \
	    || curl -sfS --header "JOB-TOKEN: $$CI_JOB_TOKEN" \
	         --data-urlencode "name=$(RELEASE_NAME)" \
	         --data-urlencode "description=Automated release for $${CI_COMMIT_SHA:-local}" \
	         --request PUT "$$CI_API_V4_URL/projects/$$CI_PROJECT_ID/releases/$(TAG)"; \
	  # Upload file to project uploads to obtain a URL
	  upload_json=$$(curl -sfS --header "JOB-TOKEN: $$CI_JOB_TOKEN" \
	                      -F "file=@$(TARBALL)" \
	                      "$$CI_API_V4_URL/projects/$$CI_PROJECT_ID/uploads"); \
	  asset_url=$$(printf "%s" "$$upload_json" | sed -nE "s/.*\"url\":\"([^\"]+)\".*/\\1/p"); \
	  asset_name="$(REPO_NAME)-$(VERSION).tar.gz"; \
	  # Attach upload as a Release asset link
	  curl -sfS --header "JOB-TOKEN: $$CI_JOB_TOKEN" \
	    --data-urlencode "name=$$asset_name" \
	    --data-urlencode "url=$${CI_SERVER_URL:-$$(dirname $$CI_API_V4_URL)}/$${CI_PROJECT_PATH}/-/$$asset_url" \
	    --request POST "$$CI_API_V4_URL/projects/$$CI_PROJECT_ID/releases/$(TAG)/assets/links" \
	    >/dev/null; \
	  echo "Release updated with asset: $$asset_name"; \
	'
endif

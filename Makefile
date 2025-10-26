# Use bash for nicer scripting
SHELL := /bin/bash
.DEFAULT_GOAL := help

# === Versioning / names ===
VERSION_SHORT := $(shell bash -c 'set -euo pipefail; \
  if [[ -n "$${CI_COMMIT_SHA:-}" ]]; then echo "$$CI_COMMIT_SHA" | cut -c1-8; \
  else git rev-parse --short=8 HEAD; fi')

REPO_NAME := $(shell basename "$$(git rev-parse --show-toplevel)")
ARTIFACTS_DIR := artifacts
TARBALL := $(ARTIFACTS_DIR)/$(REPO_NAME)-$(VERSION_SHORT).tar.gz

TAR_INCLUDE := .
TAR_EXCLUDES := --exclude .git --exclude $(ARTIFACTS_DIR)

# Tag/release metadata
TAG_PREFIX ?= v
TAG := $(TAG_PREFIX)$(VERSION_SHORT)
RELEASE_NAME := $(REPO_NAME) $(TAG)

# Git config (override as needed)
GIT_REMOTE ?= origin

.PHONY: help bootstrap lint test build run clean clean-all package version release

help: ## Show this help
	@grep -E '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) \
	 | sed -E 's/:.*?## /:\t/' \
	 | sort

bootstrap: ## Install local dev deps (example placeholder)
	@echo "No bootstrap steps defined yet."

lint: ## Run linters (example placeholder)
	@echo "Running linters…"

test: ## Run test suite (example placeholder)
	@echo "Running tests…"

build: lint test ## Build your project (example placeholder)
	@echo "Building…"

run: build ## Run the app locally (example placeholder)
	@echo "Running app…"

version: ## Print the computed version
	@echo $(VERSION_SHORT)

package: ## Create versioned tarball in artifacts/
	@mkdir -p $(ARTIFACTS_DIR)
	@echo "Packaging $(REPO_NAME) -> $(TARBALL)"
	@tar -czf $(TARBALL) $(TAR_EXCLUDES) $(TAR_INCLUDE)
	@echo "Created $(TARBALL)"

# Keep only the 5 most recent tarballs; delete the rest (safe even if <5 exist)
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

# Create a Git tag, package, and (in CI) publish a GitLab Release + attach tarball
release: package ## Tag repo and publish GitLab Release with tarball (in CI)
	@echo "Tagging repository with $(TAG)…"
	@bash -c 'set -euo pipefail; \
	  if ! git rev-parse "$(TAG)" >/dev/null 2>&1; then \
	    git tag -a "$(TAG)" -m "Release $(TAG)"; \
	    git push $(GIT_REMOTE) "$(TAG)"; \
	  else \
	    echo "Tag $(TAG) already exists."; \
	  fi'
	@bash -c 'set -euo pipefail; \
	  if [[ -n "$${CI_JOB_TOKEN:-}" && -n "$${CI_API_V4_URL:-}" && -n "$${CI_PROJECT_ID:-}" ]]; then \
	    echo "Creating/updating GitLab Release $(TAG) and uploading asset…"; \
	    # Create or update Release
	    curl -sfS --header "JOB-TOKEN: $$CI_JOB_TOKEN" \
	      --data-urlencode "name=$(RELEASE_NAME)" \
	      --data-urlencode "tag_name=$(TAG)" \
	      --data-urlencode "description=Automated release for $$CI_COMMIT_SHA" \
	      --request POST "$$CI_API_V4_URL/projects/$$CI_PROJECT_ID/releases" \
	      || curl -sfS --header "JOB-TOKEN: $$CI_JOB_TOKEN" \
	           --data-urlencode "name=$(RELEASE_NAME)" \
	           --data-urlencode "description=Automated release for $$CI_COMMIT_SHA" \
	           --request PUT "$$CI_API_V4_URL/projects/$$CI_PROJECT_ID/releases/$(TAG)"; \
	    # Upload the file to project uploads to get a URL
	    upload_json=$$(curl -sfS --header "JOB-TOKEN: $$CI_JOB_TOKEN" \
	                      -F "file=@$(TARBALL)" \
	                      "$$CI_API_V4_URL/projects/$$CI_PROJECT_ID/uploads"); \
	    asset_url=$$(echo "$$upload_json" | sed -nE 's/.*"url":"([^"]+)".*/\1/p'); \
	    asset_name="$(REPO_NAME)-$(VERSION_SHORT).tar.gz"; \
	    # Attach upload as a Release asset link
	    curl -sfS --header "JOB-TOKEN: $$CI_JOB_TOKEN" \
	      --data-urlencode "name=$$asset_name" \
	      --data-urlencode "url=$${CI_SERVER_URL:-$$(dirname $$CI_API_V4_URL)}/$${CI_PROJECT_PATH}/-/$$asset_url" \
	      --request POST "$$CI_API_V4_URL/projects/$$CI_PROJECT_ID/releases/$(TAG)/assets/links" \
	      >/dev/null; \
	    echo "Release updated with asset: $$asset_name"; \
	  else \
	    echo "Not in GitLab CI with API env; release asset upload skipped."; \
	  fi'

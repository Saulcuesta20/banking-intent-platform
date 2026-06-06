DOCKER_API_VERSION ?= 1.44
DOCKER ?= docker
APP_IMAGE ?= banking-intent-platform-app
APP_CONTAINER ?= banking-intent-app
NEO4J_CONTAINER ?= banking-intent-neo4j
NEO4J_COMPOSE_CONTAINER ?= banking-intent-platform-neo4j-1
DOCKER_NETWORK ?= banking-intent-net
NEO4J_VOLUME ?= banking-intent-neo4j-data
PYTHON ?= .venv/bin/python
FLOW ?= money.transfer
DEPTH ?= 3
DATA ?= {}
PROVIDER ?= openai
MODEL ?=

ifneq (,$(wildcard .env))
include .env
export
endif

.PHONY: docker-network app-image platform-up up databases-up databases-ps neo4j-up neo4j-ps neo4j-logs neo4j-stop neo4j-down app-up app-ps app-logs app-stop ingest ingest-graph extract extract-enterprise-dump extract-enterprise-dump-apply extract-instructions extract-langgraph extract-apply graph-tree graph-tree-all test

docker-network:
	@$(DOCKER) network inspect $(DOCKER_NETWORK) >/dev/null 2>&1 || $(DOCKER) network create $(DOCKER_NETWORK)

app-image:
	@$(DOCKER) build --quiet -t $(APP_IMAGE) . >/dev/null 2>&1

platform-up: docker-network neo4j-up app-up

up: platform-up

databases-up: docker-network
	$(DOCKER) compose --profile optional up -d neo4j qdrant postgres redis
	-$(DOCKER) network connect --alias qdrant $(DOCKER_NETWORK) banking-intent-platform-qdrant-1 >/dev/null 2>&1
	-$(DOCKER) network connect --alias postgres $(DOCKER_NETWORK) banking-intent-platform-postgres-1 >/dev/null 2>&1
	-$(DOCKER) network connect --alias redis $(DOCKER_NETWORK) banking-intent-platform-redis-1 >/dev/null 2>&1
	-$(DOCKER) network connect --alias $(NEO4J_CONTAINER) $(DOCKER_NETWORK) $(NEO4J_COMPOSE_CONTAINER) >/dev/null 2>&1

databases-ps:
	$(DOCKER) compose --profile optional ps neo4j qdrant postgres redis


neo4j-up: docker-network
	@$(DOCKER) volume inspect $(NEO4J_VOLUME) >/dev/null 2>&1 || $(DOCKER) volume create $(NEO4J_VOLUME)
	@if $(DOCKER) ps -a --format '{{.Names}}' | grep -qx '$(NEO4J_CONTAINER)'; then \
		$(DOCKER) start $(NEO4J_CONTAINER) >/dev/null; \
	elif $(DOCKER) ps -a --format '{{.Names}}' | grep -qx '$(NEO4J_COMPOSE_CONTAINER)'; then \
		$(DOCKER) start $(NEO4J_COMPOSE_CONTAINER) >/dev/null; \
		$(DOCKER) network connect --alias $(NEO4J_CONTAINER) $(DOCKER_NETWORK) $(NEO4J_COMPOSE_CONTAINER) >/dev/null 2>&1 || true; \
	else \
		$(DOCKER) run -d --name $(NEO4J_CONTAINER) --network $(DOCKER_NETWORK) -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=$(NEO4J_USER)/$(NEO4J_PASSWORD) -v $(NEO4J_VOLUME):/data neo4j:5-community >/dev/null; \
	fi

neo4j-ps:
	$(DOCKER) ps -a --filter name=$(NEO4J_CONTAINER) --filter name=$(NEO4J_COMPOSE_CONTAINER)

neo4j-logs:
	$(DOCKER) logs $(NEO4J_CONTAINER)

neo4j-stop:
	$(DOCKER) stop $(NEO4J_CONTAINER)

neo4j-down:
	-$(DOCKER) stop $(APP_CONTAINER) $(NEO4J_CONTAINER)
	-$(DOCKER) rm $(APP_CONTAINER) $(NEO4J_CONTAINER)

app-up: docker-network app-image
	@if $(DOCKER) ps -a --format '{{.Names}}' | grep -qx '$(APP_CONTAINER)'; then \
		$(DOCKER) rm -f $(APP_CONTAINER) >/dev/null; \
	fi
	$(DOCKER) run -d --name $(APP_CONTAINER) --network $(DOCKER_NETWORK) -p 8000:8000 -v $(PWD):/app -w /app -e PYTHONPATH=/app -e USE_AI_PROVIDERS -e OPENAI_API_KEY -e OPENAI_BASE_URL -e INTENT_LLM_MODEL -e NEO4J_URI=bolt://$(NEO4J_CONTAINER):7687 -e NEO4J_USER -e NEO4J_PASSWORD $(APP_IMAGE) >/dev/null

app-ps:
	$(DOCKER) ps -a --filter name=$(APP_CONTAINER)

app-logs:
	$(DOCKER) logs $(APP_CONTAINER)

app-stop:
	$(DOCKER) stop $(APP_CONTAINER)

ingest:
	$(PYTHON) -m app.cli.ingest data/raw

ingest-graph: require-openai-key neo4j-up app-image
	$(DOCKER) run --rm --network $(DOCKER_NETWORK) -v $(PWD):/app -w /app -e PYTHONPATH=/app -e OPENAI_API_KEY -e OPENAI_BASE_URL -e INTENT_LLM_MODEL -e NEO4J_URI=bolt://$(NEO4J_CONTAINER):7687 -e NEO4J_USER -e NEO4J_PASSWORD $(APP_IMAGE) python tools/extract_flows_from_corpus.py --raw-dir data/raw --apply --clean

extract: require-openai-key
	$(PYTHON) tools/extract_flows_from_corpus.py --raw-dir data/raw

extract-enterprise-dump: require-openai-key
	$(PYTHON) tools/extract_flows_from_corpus.py --raw-dir data/raw/enterprise_dump_2026 --build-extraction-instructions --require-human-review

extract-enterprise-dump-apply: require-openai-key
	$(PYTHON) tools/extract_flows_from_corpus.py --raw-dir data/raw/enterprise_dump_2026 --build-extraction-instructions --require-human-review --apply

extract-instructions: require-openai-key
	$(PYTHON) tools/extract_flows_from_corpus.py --raw-dir data/raw --build-extraction-instructions

extract-langgraph: require-openai-key
	$(PYTHON) tools/extract_flows_from_corpus.py --raw-dir data/raw --max-validation-retries 1 --require-human-review

extract-apply: require-openai-key
	$(PYTHON) tools/extract_flows_from_corpus.py --raw-dir data/raw --apply

graph-tree: neo4j-up app-image
	$(DOCKER) run --rm --network $(DOCKER_NETWORK) -v $(PWD):/app -w /app -e PYTHONPATH=/app -e NEO4J_URI=bolt://$(NEO4J_CONTAINER):7687 -e NEO4J_USER -e NEO4J_PASSWORD $(APP_IMAGE) python tools/neo4j_tree.py --source $(FLOW) --depth $(DEPTH)

graph-tree-all: neo4j-up app-image
	$(DOCKER) run --rm --network $(DOCKER_NETWORK) -v $(PWD):/app -w /app -e PYTHONPATH=/app -e NEO4J_URI=bolt://$(NEO4J_CONTAINER):7687 -e NEO4J_USER -e NEO4J_PASSWORD $(APP_IMAGE) python tools/neo4j_tree.py --depth $(DEPTH)

test:
	$(PYTHON) -m pytest
